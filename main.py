import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ui.app import FPGAInsightApp

if __name__ == "__main__":
    app = FPGAInsightApp()
    app.mainloop()
