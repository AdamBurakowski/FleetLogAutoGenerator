from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsOpacityEffect, QPushButton, QFileDialog, QFrame,
    QLineEdit, QFormLayout, QGroupBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtGui import (
    QAction, QPixmap, QIcon, QKeySequence, QShortcut
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QDate
)
import pandas as pd

from raport_generation import raport_generate


class DropArea(QFrame):
    def __init__(self, on_error):
        super().__init__()
        self.setObjectName("dropAreaFrame")
        self.setAcceptDrops(True)
        self.on_error = on_error

        self.setStyleSheet("""
            #dropAreaFrame {
                background-color: #c7c7c7;
            }
            #dropButton {
                padding: 6px 12px;
            }
        """)

        layout = QVBoxLayout()
        self.label = QLabel("Drop a .csv file here or browse")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.browse_button = QPushButton("Browse Files")
        self.browse_button.setObjectName("dropButton")
        self.browse_button.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.browse_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)
        self.file_path = None

    def set_file(self, file_path):
        self.file_path = file_path
        self.label.setText(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".csv"):
                event.acceptProposedAction()
            else:
                event.ignore()
                self.on_error("The file needs to have .csv extension!")
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(".csv"):
                self.set_file(file_path)
            else:
                self.on_error("The file needs to have .csv extension!")

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if file_path:
            if file_path.lower().endswith(".csv"):
                self.set_file(file_path)
            else:
                self.on_error("The file needs to have .csv extension!")


class FormArea(QGroupBox):
    def __init__(self, main_window):
        super().__init__()
        self.init_ui()
        self.main_window = main_window
        self.id_person_map = self.main_window.id_person_map

    def init_ui(self):
        layout = QFormLayout()
        self.id_input = QLineEdit()

        layout.addRow("Pojazd:", self.id_input)
        self.user_input = QLineEdit()

        layout.addRow("Podatnik:", self.user_input)
        date_widget = QWidget()

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.setDate(QDate.currentDate())  # default to today

        self.finish_date = QDateEdit()
        self.finish_date.setCalendarPopup(True)
        self.finish_date.setDisplayFormat("dd.MM.yyyy")
        self.finish_date.setDate(QDate.currentDate())

        self.start_date.dateChanged.connect(
            lambda date: self.finish_date.setMinimumDate(date)
        )

        def on_finish_date_changed(date):
            if date < self.start_date.date():
                self.finish_date.blockSignals(True)  # avoid recursion
                self.finish_date.setDate(self.start_date.date())
                self.finish_date.blockSignals(False)

        self.finish_date.dateChanged.connect(on_finish_date_changed)

        h_layout.addWidget(self.start_date)
        h_layout.addWidget(self.finish_date)

        date_widget.setLayout(h_layout)
        layout.addRow("Start Date / Finish Date:", date_widget)

        self.setLayout(layout)

    def get_id(self):
        return self.id_input.text()

    def set_id(self, value):
        self.id_input.setText(value)

    def get_user(self):
        return self.user_input.text()

    def set_user(self, value):
        self.user_input.setText(value)

    def get_start_date(self):
        return self.start_date.date()

    def set_start_date(self, qdate):
        self.start_date.setDate(qdate)

    def get_finish_date(self):
        return self.finish_date.date()

    def set_finish_date(self, qdate):
        self.finish_date.setDate(qdate)

class DragDropWindow(QWidget):
    def __init__(self, main_window, mode="file"):
        super().__init__()
        self.setWindowTitle("CSV File Import")
        self.setGeometry(300, 300, 400, 300)
        self.main_window = main_window
        self.mode = mode

        layout = QVBoxLayout()

        self.drop_area = DropArea(self.show_toast)
        layout.addWidget(self.drop_area)

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.on_submit)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

        # Toast notification
        self.toast_label = QLabel("", self)
        self.toast_label.setAlignment(Qt.AlignCenter)
        self.toast_label.setStyleSheet("""
            background-color: rgba(50, 50, 50, 200);
            color: white;
            padding: 8px;
            border-radius: 6px;
        """)
        self.toast_label.hide()

    def show_toast(self, message):
        self.toast_label.setText(message)
        self.toast_label.adjustSize()
        self.toast_label.move(
            (self.width() - self.toast_label.width()) // 2,
            self.height() - self.toast_label.height() - 20
        )
        self.toast_label.show()

        effect = QGraphicsOpacityEffect(self.toast_label)
        self.toast_label.setGraphicsEffect(effect)
        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(4000)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.toast_label.hide)
        self.anim.start()

    def on_submit(self):
        path = self.drop_area.file_path
        if not path:
            self.show_toast("Please select a CSV file first.")
            return
        try:
            df = pd.read_csv(path)
            if (self.mode == "file"):
                if getattr(self.main_window, "df", None) is not None:
                    self.show_toast("womp womp — MainWindow already has a DataFrame.")
                    return
                else:
                    self.main_window.df = df
                    self.main_window.add_recent_file(path)
                    self.main_window.reload_window()
            elif (self.mode == "data"):
                required_cols = {"Pojazd", "Kierowca"}
                if not required_cols.issubset(df.columns):
                    self.show_toast("CSV must contain 'Pojazd' and 'Kierowca' columns, dumbass.")
                    return

                df = df[["Pojazd", "Kierowca"]]

                csv_data = df.to_csv(index=False)
                self.main_window.settings.setValue("id_person_map_csv", csv_data)
            self.close()
        except Exception as e:
            self.show_toast(f"Failed to load CSV: {e}")
            return


class ManageIDPersonWindow(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("Manage ID/Person Data")
        self.setGeometry(400, 200, 400, 300)
        self.settings = self.main_window.settings

        layout = QVBoxLayout()

        table_container = QHBoxLayout()
        table_container.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Pojazd", "Kierowca"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setFixedWidth(300)
        table_container.addWidget(self.table)

        table_container.addStretch()
        layout.addLayout(table_container)

        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add Row")
        add_btn.clicked.connect(self.add_row)
        button_layout.addWidget(add_btn)
        del_btn = QPushButton("Delete Row")
        del_btn.clicked.connect(self.delete_row)
        button_layout.addWidget(del_btn)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_data)
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(exit_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        self.setLayout(layout)

        self.load_data()

    def load_data(self):
        df = self.main_window.load_id_person_map()
        if not df.empty:
            self.table.setRowCount(len(df))
            for row, (id_val, person_val) in enumerate(zip(df["Pojazd"], df["Kierowca"])):
                self.table.setItem(row, 0, QTableWidgetItem(str(id_val)))
                self.table.setItem(row, 1, QTableWidgetItem(str(person_val)))
        else:
            self.table.setRowCount(5)

    def save_data(self):
        rows = self.table.rowCount()
        id_list = []
        person_list = []
        for r in range(rows):
            id_item = self.table.item(r, 0)
            person_item = self.table.item(r, 1)
            if id_item and person_item:
                id_val = id_item.text().strip()
                person_val = person_item.text().strip()
                if id_val or person_val:
                    id_list.append(id_val)
                    person_list.append(person_val)

        df = pd.DataFrame({"Pojazd": id_list, "Kierowca": person_list})

        self.main_window.id_person_map = df
        self.main_window.save_id_person_map()

    def add_row(self):
        self.table.insertRow(self.table.rowCount())

    def delete_row(self):
        selected = self.table.currentRow()
        if selected >= 0:
            self.table.removeRow(selected)


class ManualExport(QGroupBox):
    def __init__(self, main_window):
        super().__init__("Manual Export")
        self.main_window = main_window
        self.setWindowTitle("Manual Export")
        self.aggregated_df = self.main_window.aggregated_df
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.driver_input = QLineEdit()
        layout.addRow(QLabel("Dane podatnika:"), self.driver_input)

        self.registration_input = QLineEdit()
        layout.addRow(QLabel("Numer rejestracyjny pojazdu samochodowego:"), self.registration_input)

        self.start_date_input = QLineEdit()
        layout.addRow(QLabel("Dzień rozpoczęcia prowadzenia ewidencji:"), self.start_date_input)

        self.end_date_input = QLineEdit()
        layout.addRow(QLabel("Dzień zakończenia prowadzenia ewidencji:"), self.end_date_input)

        self.tacho_start_input = QLineEdit()
        layout.addRow(QLabel("Stan licznika na dzień rozpoczęcia prowadzenia ewidencji (km):"), self.tacho_start_input)

        self.tacho_end_input = QLineEdit()
        layout.addRow(QLabel("Stan licznika na dzień zakończenia prowadzenia ewidencji (km):"), self.tacho_end_input)

        self.kilometers_input = QLineEdit()
        layout.addRow(QLabel("Liczba przejechanych kilometrów na dzień (km):"), self.kilometers_input)

        self.generate_btn = QPushButton("Export")
        self.generate_btn.clicked.connect(self.on_generate_report)
        layout.addRow(self.generate_btn)

        self.setLayout(layout)

    def on_generate_report(self):
        args = [
            self.registration_input.text(),
            self.driver_input.text(),
            self.start_date_input.text(),
            self.end_date_input.text(),
            self.tacho_start_input.text(),
            self.tacho_end_input.text(),
            self.kilometers_input.text()
        ]
        raport_generate(self.aggregated_df, args)


class ConfigManagement(QGroupBox):
    def __init__(self, main_window):
        super().__init__("Config")
        self.main_window = main_window
        self.setWindowTitle("Manage Config")
        self.init_ui()
        self.original_drivers_path = self.drivers_path_edit.text()  # Track original value
        self.original_exports_path = self.exports_path_edit.text()  # Track original value

    def init_ui(self):
        self.drivers_label = QLabel("Ścieżka prowadząca do mapy kierowców i pojazdów")
        self.drivers_path_edit = QLineEdit()

        saved_drivers_path = self.main_window.settings.value("drivers_data_path", "")
        self.drivers_path_edit.setText(saved_drivers_path)

        self.browse_drivers_button = QPushButton("Browse")
        self.browse_drivers_button.clicked.connect(lambda: self.browse_for_path(self.drivers_path_edit))

        self.exports_label = QLabel("Ścieżka prowadząca do miejsca zapisu raportów")
        self.exports_path_edit = QLineEdit()

        saved_exports_path = self.main_window.settings.value("export_location_path", "")
        self.exports_path_edit.setText(saved_exports_path)

        self.browse_exports_button = QPushButton("Browse")
        self.browse_exports_button.clicked.connect(lambda: self.browse_for_path(self.exports_path_edit))

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_changes)

        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.exit_config)

        drivers_layout = QHBoxLayout()
        drivers_layout.addWidget(self.drivers_path_edit)
        drivers_layout.addWidget(self.browse_drivers_button)

        exports_layout = QHBoxLayout()
        exports_layout.addWidget(self.exports_path_edit)
        exports_layout.addWidget(self.browse_exports_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.exit_button)

        v_layout = QVBoxLayout()
        v_layout.addWidget(self.drivers_label)
        v_layout.addLayout(drivers_layout)
        v_layout.addWidget(self.exports_label)
        v_layout.addLayout(exports_layout)
        v_layout.addLayout(button_layout)

        self.setLayout(v_layout)

    def browse_for_path(self, path_edit: QLineEdit):
        new_path = QFileDialog.getExistingDirectory(self, "Select Directory", path_edit.text())
        if new_path:
            path_edit.setText(new_path)

    def save_changes(self):
        new_drivers_path = self.drivers_path_edit.text()
        self.main_window.settings.setValue("drivers_data_path", new_drivers_path)
        self.original_drivers_path = new_drivers_path  # Update original after saving
        new_exports_path = self.exports_path_edit.text()
        self.main_window.settings.setValue("export_location_path", new_exports_path)
        self.original_exports_path = new_exports_path  # Update original after saving
        QMessageBox.information(self, "Saved", "Configuration has been saved.")

    def exit_config(self):
        if self.drivers_path_edit.text() != self.original_drivers_path:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.save_changes()
                self.close()
            elif reply == QMessageBox.No:
                self.close()
            else:
                return
        else:
            self.close()

