
import sys

from PyQt5.QtWidgets import QApplication
from forms.persons import PersonsForm


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = PersonsForm()
    window.show()

    sys.exit(app.exec_())
