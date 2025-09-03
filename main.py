from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QMainWindow, QTableView,
    QMenu, QMessageBox, QSplitter, QSizePolicy
)
from PySide6.QtGui import (
    QAction, QPixmap, QIcon, QKeySequence, QShortcut
)
from PySide6.QtCore import (
    Qt, QDate, QSettings, QSize,
    QStandardPaths, QCoreApplication
)
import sys
import os
import pandas as pd

from raport_generation import (
    aggregate_trips, raport_generate
)
from windows import (
    DropArea, FormArea, DragDropWindow,
    ManageIDPersonWindow, ManualExport,
    ConfigManagement
)
from backend import (
    proxy_to_df, IDFilterProxyModel, PandasModel
)


class MainWindow(QMainWindow):
    def __init__(self, df=None):
        super().__init__()
        QCoreApplication.setOrganizationName("AdamBurakowski")
        QCoreApplication.setApplicationName("FleetLogAutoGenerator")
        self.settings = QSettings()
        self.recent_files = self.load_recent_files()
        self.id_person_map = self.load_id_person_map()

        self.df = df
        self.filename = None  # Name of most recently saved file

        self.setWindowTitle("FLAG")
        self.child_windows = []

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        if df is None:
            self.show_recent_files()

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        new_action = QAction("Open", self)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        export_action = QAction("Export", self)
        export_action.triggered.connect(lambda: self.save_file_as(True))
        file_menu.addAction(export_action)

        export_pdf_action = QAction("Export to PDF", self)
        export_pdf_action.triggered.connect(self.export_as_pdf)
        file_menu.addAction(export_pdf_action)

        export_pdf_man_action = QAction("Export to PDF Manually", self)
        export_pdf_man_action.triggered.connect(self.manual_export)
        file_menu.addAction(export_pdf_man_action)

        data_menu = menu_bar.addMenu("Data")

        import_csv_action = QAction("Import from CSV", self)
        import_csv_action.triggered.connect(self.import_csv_window)
        data_menu.addAction(import_csv_action)

        manage_action = QAction("Manage", self)
        manage_action.triggered.connect(self.manage_id_person_window)
        data_menu.addAction(manage_action)

        config_menu = menu_bar.addMenu("Config")

        manage_config_action = QAction("Manage", self)
        manage_config_action.triggered.connect(self.manage_config)
        config_menu.addAction(manage_config_action)

    def manage_config(self):
        config_window = ConfigManagement(self)
        config_window.show()
        self.child_windows.append(config_window)

    def import_csv_window(self):
        new_window = DragDropWindow(self, "data")
        new_window.show()
        self.child_windows.append(new_window)

    def manage_id_person_window(self):
        manage_window = ManageIDPersonWindow(self)
        manage_window.show()
        self.child_windows.append(manage_window)

    def save_id_person_map(self):
        csv_file = self.get_drivers_data_path()
        self.id_person_map.to_csv(csv_file, index=False)

    def load_id_person_map(self):
        csv_file = self.get_drivers_data_path()
        if os.path.exists(csv_file):
            return pd.read_csv(csv_file)
        df = pd.DataFrame(columns=["Pojazd", "Kierowca"])
        df.to_csv(csv_file, index=False)
        return df

    def get_drivers_data_path(self):
        # Sets Path to the QSettings directory if None
        path = self.settings.value("drivers_data_path", "")
        if not path:
            # Gets the platform specific directory
            path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
            os.makedirs(path, exist_ok=True)
            self.settings.setValue("drivers_data_path", path)
        return os.path.join(path, "id_person_map.csv")

    def new_file(self):
        new_window = DragDropWindow(self)
        new_window.show()
        self.child_windows.append(new_window)

    def save_file(self):
        if not hasattr(self, "model") or self.model is None:
            print("No data to save.")
            return
        if self.filename is None:
            self.save_file_as()
        else:
            try:
                self.model._df.to_csv(self.filename, index=False)
                print(f"Saved to {self.filename}")
            except Exception as e:
                print(f"Failed to save: {e}")

    def save_file_as(self, export=False):
        # Decide which DataFrame to save
        if export:
            if not hasattr(self, "aggregated_df") or self.aggregated_df is None:
                print("No generated data to export.")
                return
            df_to_save = self.aggregated_df
        else:
            if not hasattr(self, "model") or self.model is None:
                print("No data to save.")
                return
            df_to_save = self.model._df

        # Ask user for file path
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if path:
            try:
                df_to_save.columns = [col.replace('\n', ' ').replace('\r', ' ') if isinstance(col, str) else col
                      for col in df_to_save.columns]

                df_to_save.to_csv(path, index=False)
                if not export:
                    self.filename = path
                    print(f"Saved as {path}")
                else:
                    print(f"Exported as {path}")
            except Exception as e:
                print(f"Failed to save: {e}")

    def export_as_pdf(self):
        id_val = self.form_area.get_id()
        user_val = self.form_area.get_user()
        start_date_qdate = self.form_area.get_start_date()
        finish_date_qdate = self.form_area.get_finish_date()

        if id_val and user_val and start_date_qdate.isValid() and finish_date_qdate.isValid():
            start_date = start_date_qdate.toString("dd.MM.yyyy")
            finish_date = finish_date_qdate.toString("dd.MM.yyyy")
            args = [id_val, user_val, start_date, finish_date]
        else:
            args = []

        path = self.settings.value("export_location_path", "")

        raport_generate(self.aggregated_df, args, path)

    def manual_export(self):
        new_window = ManualExport(self)
        new_window.show()
        self.child_windows.append(new_window)

    def toggle_lock(self):
        if not hasattr(self, "model") or self.model is None:
            return
        new_state = not self.model.is_locked()
        self.model.set_locked(new_state)
        try:
            self.generated_model.set_locked(not new_state)
        except AttributeError:
            pass
        self.lock_button.setText("Unlock" if new_state else "Lock")

    def generate_action(self):
        filtered_df = proxy_to_df(self.proxy_model)
        self.aggregated_df = aggregate_trips(filtered_df)

        self.generated_model = PandasModel(self.aggregated_df, locked=True)

        if hasattr(self, "generated_table"):
            self.right_layout.removeWidget(self.generated_table)
            self.generated_table.deleteLater()

        self.generated_table = QTableView()
        self.generated_table.setModel(self.generated_model)

        self.right_layout.addWidget(self.generated_table)

    def reload_window(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.form_area = FormArea(self)
        self.form_area.id_input.textChanged.connect(self.update_user)
        self.form_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        main_layout.addWidget(self.form_area)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        if self.df is not None:
            table_view = QTableView()
            self.model = PandasModel(self.df)
            self.proxy_model = IDFilterProxyModel()
            self.proxy_model.setSourceModel(self.model)
            self.proxy_model.date_col_index = self.df.columns.get_loc("Data i Godzina")
            filtered_df = proxy_to_df(self.proxy_model)

            undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), table_view)
            undo_shortcut.activated.connect(self.model.undo)

            redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), table_view)
            redo_shortcut.activated.connect(self.model.redo)

            id_col_index = self.df.columns.get_loc("Pojazd")
            self.proxy_model.setFilterKeyColumn(id_col_index)
            self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

            table_view.setModel(self.proxy_model)
            table_view.resizeColumnsToContents()
            table_view.setContextMenuPolicy(Qt.CustomContextMenu)

            self.form_area.id_input.textChanged.connect(self.update_id_filter)
            self.form_area.start_date.dateChanged.connect(self.update_date_filter)
            self.form_area.finish_date.dateChanged.connect(self.update_date_filter)

            def open_menu(pos):
                index = table_view.indexAt(pos)
                if index.isValid():
                    menu = QMenu()
                    revert_action = QAction("Revert cell", self)
                    revert_action.triggered.connect(
                        lambda: self.model.revert_cell(index.row(), index.column())
                    )
                    menu.addAction(revert_action)

                    insert_above_action = QAction("Insert row above", self)
                    insert_above_action.triggered.connect(
                        lambda: self.model.insert_row(
                            index, copy_columns=["Pojazd", "Data i Godzina"]
                        )
                    )
                    menu.addAction(insert_above_action)

                    insert_below_action = QAction("Insert row below", self)
                    insert_below_action.triggered.connect(
                        lambda: self.model.insert_row(
                            index.siblingAtRow(index.row() + 1),
                            copy_columns=["Pojazd", "Data i Godzina"]
                        )
                    )
                    menu.addAction(insert_below_action)

                    delete_action = QAction("Delete row", self)
                    delete_action.triggered.connect(
                        lambda: self.model.delete_row(index.row())
                    )
                    menu.addAction(delete_action)

                    menu.exec(table_view.viewport().mapToGlobal(pos))

            table_view.customContextMenuRequested.connect(open_menu)

            left_layout.addWidget(table_view)
        else:
            left_layout.addWidget(QLabel("No DataFrame loaded."))

        splitter.addWidget(left_widget)
        right_widget = QWidget()
        self.right_layout = QVBoxLayout(right_widget)

        button_row = QHBoxLayout()

        self.lock_button = QPushButton("Lock" if not self.model.is_locked() else "Unlock")
        self.lock_button.clicked.connect(self.toggle_lock)
        button_row.addWidget(self.lock_button)

        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self.generate_action)
        button_row.addWidget(self.generate_button)

        self.right_layout.addLayout(button_row)

        splitter.addWidget(right_widget)

        splitter.setSizes([550, 450])

        main_layout.addWidget(splitter)

        self.setCentralWidget(central_widget)
        self.update_date_range()

    def update_date_filter(self):
        start = self.form_area.start_date.date()
        end = self.form_area.finish_date.date()
        self.proxy_model.set_date_range(start, end)

    def update_id_filter(self, text):
        self.proxy_model.filter_text = text
        self.proxy_model.invalidateFilter()

    def update_date_range(self):
        if self.df is None or self.proxy_model.rowCount() == 0:
            return

        date_col_index = self.df.columns.get_loc("Data i Godzina")
        visible_dates = []

        for row in range(self.proxy_model.rowCount()):
            index = self.proxy_model.index(row, date_col_index)
            value = self.proxy_model.data(index)
            if value:
                dt = pd.to_datetime(value, format="%d.%m.%Y %H:%M", errors='coerce')
                if dt is not pd.NaT:
                    visible_dates.append(dt.date())

        if not visible_dates:
            return

        min_date = min(visible_dates)
        max_date = max(visible_dates)

        self.form_area.start_date.blockSignals(True)
        self.form_area.finish_date.blockSignals(True)

        self.form_area.start_date.setDate(QDate(min_date.year, min_date.month, min_date.day))
        self.form_area.finish_date.setDate(QDate(max_date.year, max_date.month, max_date.day))

        self.form_area.start_date.blockSignals(False)
        self.form_area.finish_date.blockSignals(False)

    def update_user(self, text):
        if not hasattr(self, "id_person_map") or self.id_person_map.empty:
            return
        id_to_person = dict(zip(self.id_person_map["Pojazd"], self.id_person_map["Kierowca"]))
        person = id_to_person.get(text)
        if person is not None:
            self.form_area.user_input.setText(person)

    def load_recent_files(self):
        files = self.settings.value("recentFiles", [])
        if isinstance(files, str):
            # If a single string is stored, wrap it in a list
            files = [files]
        if not isinstance(files, list):
            files = []
        # Only keep files that still exist
        return [f for f in files if f and os.path.isfile(f)]

    def save_recent_files(self):
        self.settings.setValue("recentFiles", self.recent_files)

    def add_recent_file(self, file_path):
        if not os.path.isfile(file_path):
            return
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)  # add to start
        self.recent_files = self.recent_files[:5]  # keep max 5
        self.save_recent_files()
        self.show_recent_files()

    def show_recent_files(self):
        container_layout = QVBoxLayout()

        if not self.recent_files:
            container_layout.addWidget(QLabel("No recent files"))
        else:
            container_layout.addWidget(QLabel("Recently used files:"))

            row_layout = QHBoxLayout()

            for file_path in self.recent_files:
                file_layout = QVBoxLayout()

                icon_btn = QPushButton()
                pixmap = QPixmap("file_icon.png").scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon_btn.setIcon(QIcon(pixmap))
                icon_btn.setIconSize(QSize(128, 128))
                icon_btn.setFlat(True)
                icon_btn.clicked.connect(lambda _, f=file_path: self.open_recent_file(f))
                file_layout.addWidget(icon_btn, alignment=Qt.AlignHCenter)

                file_label = QLabel(os.path.basename(file_path))
                file_label.setAlignment(Qt.AlignHCenter)
                file_layout.addWidget(file_label)

                row_layout.addLayout(file_layout)

            container_layout.addLayout(row_layout)

        container = QWidget()
        container.setLayout(container_layout)
        self.setCentralWidget(container)

    def open_recent_file(self, file_path):
        try:
            df = pd.read_csv(file_path)
            self.df = df
            self.reload_window()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file:\n{e}")


def update_date_range(self):
    if self.df is None or self.proxy_model.rowCount() == 0:
        return

    date_col_index = self.df.columns.get_loc("Date")
    visible_dates = []

    for row in range(self.proxy_model.rowCount()):
        index = self.proxy_model.index(row, date_col_index)
        value = self.proxy_model.data(index)
        if value:
            # Parsing text to data
            dt = pd.to_datetime(value, format="%d.%m.%Y %H:%M", errors='coerce')
            if dt is not pd.NaT:
                visible_dates.append(dt.date())  # cut the H:M part

    if not visible_dates:
        return

    min_date = min(visible_dates)
    max_date = max(visible_dates)

    self.form_area.start_date.blockSignals(True)
    self.form_area.finish_date.blockSignals(True)

    self.form_area.start_date.setDate(QDate(min_date.year, min_date.month, min_date.day))
    self.form_area.finish_date.setDate(QDate(max_date.year, max_date.month, max_date.day))

    self.form_area.start_date.blockSignals(False)
    self.form_area.finish_date.blockSignals(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())

