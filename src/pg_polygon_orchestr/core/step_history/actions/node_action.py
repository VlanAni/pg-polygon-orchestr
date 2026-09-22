from .action import Action


class NodeAction(Action):
    DEPLOY = 1
    REMOVE = 2
    START = 3
    STOP = 4
    EXEC = 5
    UPDATE = 6
