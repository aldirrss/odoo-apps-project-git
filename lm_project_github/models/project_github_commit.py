from odoo import fields, models, api


class ProjectGithubCommit(models.Model):
    _name = 'project.github.commit'
    _description = 'Project Github Commit'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Commit Message', help='Message associated with the commit')
    date = fields.Datetime(string='Commit Date', help='Date of the commit', default=fields.Datetime.now)
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        help='Project associated with this commit',
    )
    task_id = fields.Many2one(
        'project.task',
        string='Linked Task',
        help='Task in Odoo that is linked to this commit'
    )
    commit_hash = fields.Char(
        string='Commit',
        help='Unique identifier for the commit'
    )
    author_name = fields.Char(string='Author Name')
    author_email = fields.Char(string='Author Email')
    commiter_name = fields.Char(string='Committer Name')
    commiter_email = fields.Char(string='Committer Email')
    commit_url = fields.Char(string='Commit URL', help='URL to view the commit in the repository')
    branch_ids = fields.Many2many(
        'project.github.branch',
        string='Branches',
        help='Branches that contain this commit'
    )

    def action_view_external_commit(self):
        self.ensure_one()
        if self.commit_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.commit_url,
                'target': 'new',
            }
        return False
