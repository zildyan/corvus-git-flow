#!/usr/bin/python

from sys import exit, argv
from subprocess import Popen, PIPE


class GitError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


RETURN_RESPONSE = True
NEW_BRANCH_CREATED = 'Successfully created %s branch\n'
REPOSITORY_NOT_PREPARED = 'Repository contains branches other than master\n'
PROD = 'PROD'
RELEASE = 'RELEASE'
DEVELOP = 'DEVELOP'
STABLE = 'STABLE'
HISTORY = 'HISTORY'

def formatted(string_value):
    return '\n'.join(string_value)


def execute(command, return_response=False):
    git_query = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    (git_response, error) = git_query.communicate()

    if git_query.poll() == 0:
        if return_response is False:
            return
        elif return_response is True:
            git_response = git_response.decode()
            return formatted(git_response.splitlines())
        else:
            raise GitError('Unexisting execute option')
    else:
        error = error.decode()
        raise GitError(formatted(error.splitlines()))


def git_initialization(master, version):
    try:
        if git_repository_prepared(master) is not True:
            return REPOSITORY_NOT_PREPARED

        for branch in [PROD, RELEASE, DEVELOP, STABLE, HISTORY]:
            git_new_branch(branch, master)
            git_checkout(branch)
            if branch in [PROD, RELEASE, DEVELOP]:
                git_squash_all_commits(version)
            if branch in [RELEASE, STABLE, HISTORY]:
                git_tag(version)
            # git_push_origin(branch)

        # git_push_origin(':%s' % master)
        # git_delete_branch(master)

    except GitError:
        raise


def git_repository_prepared(master):
    try:
        if execute('git branch', RETURN_RESPONSE) == '* ' + master:
            return True
        return False

    except GitError:
        raise


def git_squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, RETURN_RESPONSE)
    execute('git reset %s' % commit_sha)


def git_tag(tag):
    execute('git tag -a %s -m "%s"' % (tag, tag))


def git_push_origin(branch):
    execute('git push origin %s' % branch)


def git_current_branch():
    return execute('git rev-parse --abbrev-ref HEAD', RETURN_RESPONSE)


def git_checkout(branch):
    execute('git checkout ' + branch)


def git_new_branch(name, main_branch):
    execute('git branch %s %s' % (name, main_branch))


def git_delete_branch(name):
    execute('git branch -D %s' % name)


def git_make_branch(name, branch_type, main_branch=None):
    try:
        current_branch = git_current_branch()
        if main_branch is None:
            main_branch = current_branch

        branch_full_name = '%s/%s' % (branch_type, name)
        git_new_branch(branch_full_name, main_branch)

        if current_branch == main_branch:
            git_checkout('%s/%s' % (branch_type, name))
        return NEW_BRANCH_CREATED % branch_full_name

    except GitError:
        raise


def git_new_bugfix(name):
    git_make_branch(name, 'BUGFIX', 'STABLE')


def git_new_feature(name):
    git_make_branch(name, 'FEATURE', 'STABLE')


def git_new_hotfix(name):
    git_make_branch(name, 'HOTFIX', 'PROD')


def git_new_junk(name):
    git_make_branch(name, 'JUNK')


def git_commit(mesagge):
    execute('git commit -m ' + mesagge)


def git_status():
    return execute('git status', RETURN_RESPONSE)


def main():
    try:
        print(git_status())
    except GitError as gErr:
        print(gErr.value)


if __name__ == '__main__':
    exit(main())
