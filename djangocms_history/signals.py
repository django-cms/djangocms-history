from django.dispatch import Signal


post_operation_undo = Signal("operation actions")

post_operation_redo = Signal("operation actions")
