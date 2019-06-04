import os
import sys
import argparse
import datetime

from github import Github

import logging
logging.basicConfig(level=logging.INFO)

from jirahub import GithubQuery
from jirahub import JiraQuery
from jirahub import how_issues_differ, IssueSync

__all__ = ['JPSync']



def jpp_jgbot(issues, jirarepo, jirauser, jirapass, gitkey):

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
    # Editing this to only sync one direction, github to jira

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

        '''
        for j in jira_comments:
            if j.author.name not in ['stsci.jgbot@gmail.com']:
               body = f'Comment by {j.author.displayName}: {j.body}'
               if body.strip() not in github_comments_body:
                  self.github.add_comment(body)
        '''


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
            '''
            # If the jira issue is resolved or done, close the github issue
            if jira_status in ['Done']:
                 if github_status is not 'closed':
                      self.github.change_status('closed')
            '''


class lock:

    def __init__(self, lockfile):
       self.lockfile = lockfile
    
    def __enter__(self):
       fout = open(self.lockfile, 'w')
       fout.write(str(datetime.datetime.now))
       fout.close()

    def __exit__(self):
       os.remove(self.lockfile)
       
        

def create_issues(issue_file, jirarepo, jirauser, jirapass, gitkey):
    """Check Jira and open any new issues in GitHub
       Check Github and open any new issues in Jira
    """
    j = JiraQuery(jirarepo, user=jirauser, password=jirapass)
    repo_list = ['jdaviz']
    g = Github(gitkey)
    
    with open(issue_file, mode='r') as iss_file:
        issues = iss_file.readlines()

    git_issue_numbers = [int(x.split()[1].split("/")[2]) for x in issues]
    jira_issue_numbers = [x.split()[0] for x in issues]

    with open(issue_file, mode='a') as iss_file:
        for repo_name in repo_list:
            repo = g.get_repo(f'spacetelescope/{repo_name}')
            all_git_issues = repo.get_issues(state='all',since=datetime.datetime(2019,4,25,0,0))

            for git_issue in all_git_issues:
                if git_issue.number not in git_issue_numbers and git_issue.pull_request == None:

                    print(f"working on github issues number {git_issue.number}")

                    descrip = f'This issue was created by JigiBot, [original github issue|{git_issue.html_url}] was created by github user {git_issue.user.login}\nPlease do not leave comments in this issue, all interaction should happen on the [original github issue|{git_issue.html_url}]. This JIRA issue is for sprint tracking:\n\n'
                    descrip += git_issue.body
                
                    # Create new jira issue
                    new_issue = j.jira.create_issue(project='DATJPP',
                                                    summary=git_issue.title,
                                                    description=descrip,
                                                    issuetype={'name': 'Task'},
                                                    priority={'name': 'Minor'})
                    
                    # Write new jira/github issue pair to issue file
                    iss_file.write(f'{new_issue.key} {repo_name}/issues/{git_issue.number}\n')
                    
                    # add a comment to the github issue with a link back to jira
                    git_issue.create_comment(f'This ticket is now being tracked at [{new_issue.key}]({new_issue.permalink()})')

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
    create_issues(args.issue_list, jirarepo, jirauser, jirapass, gitkey)
        
    # process for syning issues
    jpp_jgbot(issues, jirarepo, jirauser, jirapass, gitkey)

