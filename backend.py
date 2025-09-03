from PySide6.QtCore import (
    Qt, QDate, QAbstractTableModel,
    QSortFilterProxyModel, QModelIndex
)
import pandas as pd
import uuid


def proxy_to_df(proxy):
    source_model = proxy.sourceModel()
    rows = proxy.rowCount()
    cols = source_model.columnCount()
    data = []

    for row in range(rows):
        row_data = [
            source_model.data(proxy.mapToSource(proxy.index(row, col)), role=Qt.DisplayRole)
            for col in range(cols)
        ]
        data.append(row_data)

    headers = [source_model.headerData(i, Qt.Horizontal, role=Qt.DisplayRole) for i in range(cols)]
    return pd.DataFrame(data, columns=headers)


class IDFilterProxyModel(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.filter_text = ""
        self.start_date = None
        self.end_date = None
        self.date_col_index = None

    def set_date_range(self, start: QDate, end: QDate):
        self.start_date = start
        self.end_date = end
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self.filter_text:
            column_count = self.sourceModel().columnCount()
            matched = False
            for column in range(column_count):
                index = self.sourceModel().index(source_row, column, source_parent)
                data = str(self.sourceModel().data(index))
                if self.filter_text.lower() in data.lower():
                    matched = True
                    break
            if not matched:
                return False

        if self.start_date and self.end_date and self.date_col_index is not None:
            index = self.sourceModel().index(source_row, self.date_col_index, source_parent)
            value = self.sourceModel().data(index)
            if value:
                dt = pd.to_datetime(value, format="%d.%m.%Y %H:%M", errors='coerce')
                if dt is pd.NaT:
                    return False
                row_date = QDate(dt.year, dt.month, dt.day)
                if row_date < self.start_date or row_date > self.end_date:
                    return False

        return True


class PandasModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame(), locked=False):
        super().__init__()
        if "_id" not in df.columns:
            df = df.copy()
            df['_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
        self._df = df.copy(deep=True)
        self._original_df = df.copy(deep=True)
        self._undo_stack = []
        self._redo_stack = []
        self._locked = locked

    def set_locked(self, locked: bool):
        self._locked = locked

    def is_locked(self):
        return self._locked

    def rowCount(self, parent=None):
        return len(self._df.index)

    def columnCount(self, parent=None):
        return len(self._df.columns) - 1  # hide _id

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            visible_col = index.column()
            actual_cols = [c for c in self._df.columns if c != "_id"]
            col_name = actual_cols[visible_col]
            return str(self._df.iat[index.row(), self._df.columns.get_loc(col_name)])
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if self._locked:
            return False
        if index.isValid() and role == Qt.EditRole:
            visible_cols = [c for c in self._df.columns if c != "_id"]
            col_name = visible_cols[index.column()]
            old_value = self._df.at[index.row(), col_name]
            if value == old_value:
                return False
            self._df.at[index.row(), col_name] = value
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            # store both old and new values
            self._undo_stack.append(('edit', index.row(), col_name, old_value, value))
            self._redo_stack.clear()
            return True
        return False

    def flags(self, index):
        base_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if not self._locked:
            base_flags |= Qt.ItemIsEditable
        return base_flags

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            visible_cols = [c for c in self._df.columns if c != "_id"]
            return str(visible_cols[section])
        else:
            return str(self._df.index[section])

    def revert_cell(self, row, col):
        if self._locked:
            return False
        visible_cols = [c for c in self._df.columns if c != "_id"]
        col_name = visible_cols[col]
        row_id = self._df.at[row, "_id"]
        old_value = self._df.at[row, col_name]
        new_value = self._original_df.loc[self._original_df['_id'] == row_id, col_name].values[0]
        if old_value == new_value:
            return
        self._df.at[row, col_name] = new_value
        index = self.index(row, col)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])
        self._undo_stack.append(('edit', row, col_name, old_value, new_value))
        self._redo_stack.clear()


    def insert_row(self, proxy_index, copy_columns=None):
        if self._locked:
            return False

        source_model = self
        row = proxy_index.row()

        if hasattr(proxy_index.model(), 'mapToSource'):
            row = proxy_index.model().mapToSource(proxy_index).row()

        new_row = pd.Series([None]*self._df.shape[1], index=self._df.columns)
        new_row['_id'] = str(uuid.uuid4())

        if copy_columns:
            for col in copy_columns:
                new_row[col] = self._df.at[row, col]

        self.beginInsertRows(QModelIndex(), row, row)
        self._df = pd.concat([
            self._df.iloc[:row],
            pd.DataFrame([new_row]),
            self._df.iloc[row:]
        ]).reset_index(drop=True)
        self._original_df = pd.concat([
            self._original_df,
            pd.DataFrame([new_row])],
            ignore_index=True)
        self.endInsertRows()
        # store inverse action for undo
        self._undo_stack.append(('insert_row', row, new_row))
        self._redo_stack.clear()


    def delete_row(self, row):
        if self._locked:
            return False
        if row < 0 or row >= len(self._df):
            return
        deleted_row_data = self._df.iloc[row].copy()
        self.beginRemoveRows(QModelIndex(), row, row)
        self._df = self._df.drop(row).reset_index(drop=True)
        self.endRemoveRows()
        # store inverse action for undo
        self._undo_stack.append(('delete_row', row, deleted_row_data))
        self._redo_stack.clear()

    def undo(self):
        if self._locked:
            return False
        if not self._undo_stack:
            return
        action = self._undo_stack.pop()
        self._apply_action(action, undo=True)

    def redo(self):
        if self._locked:
            return False
        if not self._redo_stack:
            return
        action = self._redo_stack.pop()
        self._apply_action(action, undo=False)

    def _apply_action(self, action, undo=True):
        if self._locked:
            return False
        atype = action[0]

        if atype == 'edit':
            row, col_name, old_value, new_value = action[1], action[2], action[3], action[4]
            if undo:
                self._df.at[row, col_name] = old_value
                self._redo_stack.append(('edit', row, col_name, old_value, new_value))
            else:
                self._df.at[row, col_name] = new_value
                self._undo_stack.append(('edit', row, col_name, old_value, new_value))
            index = self.index(row, [c for c in self._df.columns if c != "_id"].index(col_name))
            self.dataChanged.emit(index, index, [Qt.DisplayRole])

        elif atype == "insert_row":
            row, row_data = action[1], action[2]
            if undo:
                self.beginRemoveRows(QModelIndex(), row, row)
                row_id = row_data["_id"]
                self._df = self._df[self._df['_id'] != row_id].reset_index(drop=True)
                self.endRemoveRows()
                self._redo_stack.append(("insert_row", row, row_data))
            else:
                self.beginInsertRows(QModelIndex(), row, row)
                self._df = pd.concat([
                    self._df.iloc[:row],
                    pd.DataFrame([row_data]),
                    self._df.iloc[row:]
                ]).reset_index(drop=True)
                self._original_df = pd.concat([
                    self._original_df,
                    pd.DataFrame([row_data])],
                    ignore_index=True)
                self.endInsertRows()
                self._undo_stack.append(("insert_row", row, row_data))

        elif atype == "delete_row":
            row, row_data = action[1], action[2]
            if undo:
                self.beginInsertRows(QModelIndex(), row, row)
                self._df = pd.concat([
                    self._df.iloc[:row],
                    pd.DataFrame([row_data]),
                    self._df.iloc[row:]
                ]).reset_index(drop=True)
                self.endInsertRows()
                self._redo_stack.append(("delete_row", row, row_data))
            else:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._df = self._df.drop(row).reset_index(drop=True)
                self.endRemoveRows()
                self._undo_stack.append(("delete_row", row, row_data))

