"""Parented, visible dialogs on macOS and Windows."""
def present_dialog(window, parent):
    window.transient(parent)
    window.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_reqheight()) // 2
    window.geometry(f"+{max(0, x)}+{max(0, y)}")
    window.deiconify()
    window.lift()
    window.after_idle(window.focus_force)
