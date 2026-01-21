import multiprocessing
from gui.main_window import create_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    create_gui()