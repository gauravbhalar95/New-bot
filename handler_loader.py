import importlib
import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

HANDLERS_DIR = "handlers"

def load_handlers():
    """
    Dynamically imports all Python files in the handlers directory.
    """
    for filename in os.listdir(HANDLERS_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = f"{HANDLERS_DIR}.{filename[:-3]}"
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print(f"Loaded handler: {module_name}")

class HandlerWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        """
        Reload handlers if a file in the handlers directory is modified.
        """
        if event.src_path.endswith(".py"):
            print(f"Detected change in {event.src_path}, reloading handlers...")
            load_handlers()

def watch_handlers():
    """
    Watches the handlers directory for changes and reloads handlers dynamically.
    """
    observer = Observer()
    event_handler = HandlerWatcher()
    observer.schedule(event_handler, HANDLERS_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    print("Watching handlers for changes...")
    load_handlers()
    watch_handlers()