from django.dispatch import Signal


post_operation_undo = Signal(
    providing_args=[
        "operation",
        "actions",
    ]
)

post_operation_redo = Signal(
    providing_args=[
        "operation",
        "actions",
    ]
)
