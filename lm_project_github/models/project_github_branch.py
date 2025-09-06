from odoo import fields, models, api
from random import randint


class ProjectGithubBranch(models.Model):
    _name = 'project.github.branch'
    _description = 'Git Branch linked to a Repository'
    _order = 'name desc'

    def _get_default_color(self):
        # random color index
        return randint(1, 11)

    name = fields.Char(
        string='Branch Name',
        required=True,
        help='Name of the Git branch',
    )
    repository_id = fields.Many2one(
        'project.github.repository',
        string='Repository',
        required=True,
        ondelete='cascade',
        help='GitHub Repository associated with this branch',
    )
    protected = fields.Boolean(
        string='Protected',
        default=False,
        help='Indicates if this branch is protected',
    )
    color = fields.Integer(string='Color Index', default=_get_default_color)

    _sql_constraints = [
        ('unique_branch_repository', 'unique(name, repository_id)', 'A branch with this name already exists for the selected repository.'),
    ]
