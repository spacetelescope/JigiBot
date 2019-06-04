import os
import sys
import argparse
import datetime 

import logging
logging.basicConfig(level=logging.INFO)

from jirahub import GithubQuery
from jirahub import JiraQuery
from jirahub import how_issues_differ, IssueSync

__all__ = ['JPSync']



def jda_jgbot(issues, jirarepo, jirauser, jirapass, gitkey):

    # code for testing a specific issue
    # sync the issues between the two projects 
    #sync = JPSync(g, j, '1780', 'JP-247')
    #sync.comments()
    #sync = JPSync(g, j, '2138', 'JP-326')
    #sync.comments()
    #return 
    j = JiraQuery(jirarepo, user=jirauser, password=jirapass)

    for l in issues:
        jid, gid = l.split()
        repo, gid = gid.split('/issues/')
        g = GithubQuery(f'spacetelescope/{repo}', gitkey)

        sync = JPSync(g, j, gid, jid)
        sync.status()
        sync.comments()

    return


class JPSync(IssueSync):

    def comments(self):
        if 'comments' not in self.differences:
           return
  
        # get all the comments
        github_comments = self.github.issue.get_comments()
        jira_comments = self.jira.issue.fields.comment.comments
        github_comments_body = [g.body.strip() for g in self.github.issue.get_comments()]
        jira_comments_body = [j.body.strip() for j in self.jira.issue.fields.comment.comments]

        for g in github_comments:
            if g.user.login not in ['stscijgbot']:
               body = f'Comment by {g.user.name}: {g.body}'
               if body.strip() not in jira_comments_body:
                  self.jira.add_comment(f'Comment by {g.user.name}: {g.body}')

        for j in jira_comments:
            if j.author.name not in ['stsci.jgbot@gmail.com']:
               body = f'Comment by {j.author.displayName}: {j.body}'
               if body.strip() not in github_comments_body:
                  self.github.add_comment(body)


    def status(self):
        if 'status' not in self.differences:
           return

        if self.differences['status']:
            github_status = self.differences['status'][0]
            jira_status = self.differences['status'][1]

            # If the github status is closed, move the jira issue to resolved
            if github_status == 'closed':
                 if jira_status not in ['Done']:
                     logging.info('moving {} to Done'.format(self.jira_id))
                     self.jira.change_status('Done')
            # If the jira issue is resolved or done, close the github issue
            if jira_status in ['Done']:
                 if github_status is not 'closed':
                      self.github.change_status('closed')


class lock:

    def __init__(self, lockfile):
       self.lockfile = lockfile
    
    def __enter__(self):
       fout = open(self.lockfile, 'w')
       fout.write(str(datetime.datetime.now))
       fout.close()

    def __exit__(self):
       os.remove(self.lockfile)
       
        

def create_issues(issues, jirarepo, jirauser, jirapass, gitkey):
    """Check Jira and open any new issues in GitHub
    """
    repo_list = ['imexam', 'specviz', 'mosviz', 'stginga', 'astroimtools',
                 'cubeviz', 'gwcs', 'tweakwcs', 'jwst', 'da5-notebooks']
    j = JiraQuery(jirarepo, user=jirauser, password=jirapass)

    # Add any new issues determine the issues that are open
    jira_issues = [x.split()[0] for x in issues]
    for i in j.jira.search_issues('Project="JDA" AND Type="Bug"'):
        # check those issues against the list
        if i.key not in jira_issues:


           j.issue = i.key

           # skip issues that have been created for the report
           if j.issue.fields.issuetype.name == 'Software' or j.issue.fields.issuetype.name == 'Report':
              continue


           repo = set([r.name for r in j.issue.fields.components]).intersection(repo_list)
           print(repo)

           if repo:
              repo = repo.pop()
              g = GithubQuery(f'spacetelescope/{repo}', gitkey)
           else:
              continue
              
           if j.issue.fields.description:
              description = j.issue.fields.description
           else:
              description = j.issue.fields.summary
           body = f'Issue [{i.key}]({j.issue.permalink()}) was created by {j.issue.fields.creator}:\n\n{description}'
           # if they are not in the list, create an issue in github, 
           gid = g.repo.create_issue(j.issue.fields.summary, body=body)
           print(gid)
           # add to list and then write it back out
           with open(args.issue_list, 'a') as fout:
                fout.write(f'{i.key} {repo}/issues/{gid.number}\n')
           # add a comment to the JP project with a link back
           j.add_comment(f'This ticket is now being tracked by SCSB at [#{gid.number}|https://github.com/spacetelescope/{repo}/issues/{gid.number}]')
           # add the jira label to the github issue
           g.issue = gid.number
           g.issue.add_to_labels('jira')
           g.issue.add_to_labels('bug')



if __name__=='__main__':
    gituser = os.environ['GITUSER']
    gitkey = os.environ['GITKEY']
    gitrepo = os.environ['GITREPO']

    jirauser = os.environ['JIRAUSER']
    jirapass = os.environ['JIRAPASS']
    jirarepo = os.environ['JIRAJDA']



    lockfile = 'jdasync.lock'
    if os.path.isfile(lockfile):
       logging.info('JPSync is already running')
       sys.exit(-1)
       



    parser = argparse.ArgumentParser(description='Sync a jira project and github repository')
    parser.add_argument('issue_list', type=str, help='Github repository as [username]/[repo]')
    args = parser.parse_args()

    issues = open(args.issue_list).readlines()

    # create new issues that are produced
    create_issues(issues, jirarepo, jirauser, jirapass, gitkey)
        
    # prodcess for syning issues
    jda_jgbot(issues, jirarepo, jirauser, jirapass, gitkey)


