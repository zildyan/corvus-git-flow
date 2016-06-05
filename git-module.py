#!/usr/bin/python

from sys import exit, argv
from subprocess import Popen, PIPE


class GitError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


RETURN_RESPONSE = True
HOTFIX = 'HOTFIX'
BUGFIX = 'BUGFIX'
FEATURE = 'FEATURE'
JUNK = 'JUNK'
PROD = 'PROD'
RELEASE = 'RELEASE'
DEVELOP = 'DEVELOP'
STABLE = 'STABLE'
HISTORY = 'HISTORY'
MAIN_BRANCHES = [PROD, RELEASE, DEVELOP, STABLE, HISTORY]
DEVELOP_END_KEYWORDS = ['success', 'failed', 'forced_down']


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
            return 'Aborted: repository contains branches other than master'

        for branch in MAIN_BRANCHES:
            git_new_branch(branch, master)
            git_checkout(branch)

            if branch in [PROD, RELEASE, DEVELOP]:
                git_squash_all_commits(version)

            git_commit_amend()

            if branch in [RELEASE, STABLE, HISTORY]:
                git_tag('%s/%s' % (branch, version))

            git_push_origin(branch)

        git_delete_local_branch(master)
        return 'Set default branch on remote repository to PROD'

    except GitError:
        raise


def git_repository_prepared(master):
    try:
        remote_branches = execute('git branch -r', RETURN_RESPONSE)
        for branch in MAIN_BRANCHES:
            if branch in remote_branches:
                return False

        if execute('git branch', RETURN_RESPONSE) != '* %s' % master:
            return False

        return True

    except GitError:
        raise


def git_squash_all_commits(version):
    commit_sha = execute('git commit-tree HEAD^^{tree} -m "%s"' % version, RETURN_RESPONSE)
    execute('git reset %s' % commit_sha)


def git_commit_amend(mesagge=None):
    if mesagge is None:
        execute('git commit --amend --no-edit')
    else:
        execute('git commit --amend -m "%s"' % mesagge)


def git_tag(tag_name):
    if git_check_tag(tag_name) is True:
        raise GitError('Aborted: tag already exists')
    execute('git tag -a %s -m "%s"' % (tag_name, tag_name))


def git_push_tag(tag_name):
    if git_check_tag(tag_name) is False:
        raise GitError('Aborted: tag doesn\'t exists')
    execute('git push tag %s' % tag_name)


def git_check_tag(tag_name):
    tags = execute('git tag', RETURN_RESPONSE)
    if tag_name in tags:
        return True
    return False


def git_delete_local_tag(tag_name):
    execute('git tag -d %s' % tag_name)


def git_delete_remote_tag(tag_name):
    execute('git push --delete origin %s' % tag_name)


def git_push_origin(branch_name):
    execute('git push origin %s' % branch_name)


def git_current_branch():
    return execute('git rev-parse --abbrev-ref HEAD', RETURN_RESPONSE)


def git_checkout(branch_name):
    execute('git checkout ' + branch_name)


def git_new_branch(branch_name, main_branch):
    execute('git branch %s %s' % (branch_name, main_branch))


def git_push_branch(branch_name):
    execute('git push --set-upstream origin %s --follow-tags' % branch_name)


def git_delete_local_branch(branch_name):
    execute('git branch -D %s' % branch_name)


def git_delete_remote_branch(branch_name):
    execute('git push origin --delete %s' % branch_name)


def git_make_branch(branch_name, branch_type, main_branch=None):
    try:
        current_branch = git_current_branch()
        if main_branch is None:
            main_branch = current_branch

        branch_full_name = '%s/%s' % (branch_type, branch_name)
        git_new_branch(branch_full_name, main_branch)
        git_checkout(branch_full_name)
        git_commit_amend()
        git_tag('%s/started')

        return 'Successfully created %s branch' % branch_full_name

    except GitError:
        raise


def git_new_bugfix(branch_name):
    git_make_branch(branch_name, BUGFIX, STABLE)


def git_new_feature(branch_name):
    git_make_branch(branch_name, FEATURE, STABLE)


def git_new_hotfix(branch_name):
    git_make_branch(branch_name, HOTFIX, PROD)


def git_new_junk(branch_name):
    git_make_branch(branch_name, JUNK)


def git_dev_test():
    current_branch = git_current_branch()
    if current_branch in MAIN_BRANCHES or JUNK in current_branch:
        raise GitError('Develop test isn\'t allowed on main branches')

    if git_dev_test_in_progress() is not True:
        raise GitError('Testing in progress')

    test_num = git_test_number()
    git_checkout(current_branch)

    starting_tag = '%s/started' % current_branch
    testing_tag = '%s/testing' % current_branch
    patch_name = '%s.patch' % testing_tag

    git_tag(testing_tag)
    git_make_patch(starting_tag, testing_tag)
    git_apply_patch(patch_name, STABLE)
    git_delete_file(patch_name)
    git_add_all()
    git_commit('%s/test#%d' % (current_branch, test_num))


def git_dev_test_in_progress():
    git_checkout(DEVELOP)
    last_commit_msg = execute('git log -1 --pretty=%B', RETURN_RESPONSE)
    return check_end_keywords(last_commit_msg)


def git_test_number(branch_name):
    test = execute("git log -1 --grep='%s/' --pretty=%B" % branch_name, RETURN_RESPONSE)
    if not test:
        return 1

    test_num = test.split('#')[1]
    if check_end_keywords(test_num) is True:
        test_num = test_num.split('/')[0]

    return int(test_num)


def check_end_keywords(commit_mesagge):
    for word in DEVELOP_END_KEYWORDS:
        if word in commit_mesagge:
            return True
    return False


def git_make_patch(starting_tag, ending_tag):
    execute('git diff --full-index --binary %s %s > %s.patch' % (starting_tag, ending_tag, ending_tag))


def git_apply_patch(patch_name, branch_name):
    execute('git apply --check %s' % patch_name)
    git_checkout(branch_name)
    execute('git apply -p1 < %s' % patch_name)


def git_prolong():
    


def git_add_all():
    execute('git add --all')


def git_reset(file_name):
    execute('git reset %s' % file_name)


def git_commit(mesagge):
    execute('git commit -m ' + mesagge)


def git_delete_file(file_name):
    execute('rm %s' % file_name)


def git_status():
    return execute('git status', RETURN_RESPONSE)


def main():
    try:
        print(git_initialization(git_current_branch(), 'v1.0.0'))
    except GitError as gErr:
        print(gErr.value)


if __name__ == '__main__':
    exit(main())
