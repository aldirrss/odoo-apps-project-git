from odoo import fields, models, api
from random import randint


class ProjectTaskGitBranch(models.Model):
    _name = 'project.task.git.branch'
    _description = 'Git Branch linked to a Task'
    _order = 'name desc'

    def _get_default_color(self):
        # random color index
        return randint(1, 11)

    name = fields.Char(
        string='Branch Name',
        required=True,
        help='Name of the Git branch',
    )
    task_id = fields.Many2one(
        'project.task',
        string='Task',
        required=True,
        ondelete='cascade',
        help='Task associated with this Git branch',
    )
    default = fields.Boolean(
        string='Default Active',
        default=False,
        help='Indicates if this branch is the default active branch for the task',
    )
    protected = fields.Boolean(
        string='Protected',
        default=False,
        help='Indicates if this branch is protected',
    )
    color = fields.Integer(string='Color Index', default=_get_default_color)

    _sql_constraints = [
        ('unique_branch_per_task', 'unique(name, task_id)', 'A branch with this name already exists for the selected task.'),
    ]
