#!/usr/bin/python

from modules.git_core import *


def validate_initialization():
    validate_main_branches(False)


def validate_flow_initialized():
    validate_main_branches(True)


def validate_main_branches(need_to_exists):
    validate_directory_is_git_repository()
    for branch in MAIN_BRANCHES:
        branch_existence = validate_branch_exists(branch)

        if branch_existence is False:
            raise GitError('Abort: %s branch do not exist locally and/or on remote.' % branch)
        if branch_existence is True and not need_to_exists:
            raise GitError('Abort: %s branch already initialized.' % branch)
        if branch_existence is False and need_to_exists:
            raise GitError('Abort: %s branch do not exist.' % branch)


def validate_directory_is_git_repository():
    if 'true' not in is_inside_work_tree():
        raise GitError('Fatal: Not a git repository.')


def validate_branch_exists(branch_name):
    return find_branch(branch_name) == format_rows([branch_name, 'origin/' + branch_name])


def validate_branch():
    validate_clean_head()
    validate_sync_with_remote()
    current_branch = get_current_branch()

    if current_branch in MAIN_BRANCHES or SUPPORT in current_branch:
        raise GitError('Abort: Command isn\'t allowed on main and support branches.')

    valid_branch = False
    for branch in [HOTFIX, BUGFIX, FEATURE]:
        if current_branch.startswith(branch):
            valid_branch = True
            break

    if not valid_branch:
        raise GitError('Abort: Command isn\'t allowed on custom branches.')


def validate_sync_with_remote():
    if 'up-to-date' not in fetch_with_status():
        raise GitError('Abort: Local branch is not synchronised with remote.')


def validate_clean_head():
    get_current_branch()
    verify_head()
    verify_merge()
    update_index()
    validate_no_unstaged_changes()
    validate_no_uncommited_changes()


def validate_no_unstaged_changes():
    if unstaged_changes() != '':
        raise GitError('Abort: ')


def validate_no_uncommited_changes():
    if uncommited_changes != '':
        raise GitError('Abort: ')


def tag_exists(tag_name):
    try:
        check_tag_locally(tag_name)
        if check_tag_remotely(tag_name) != '':
            return False
    except GitError:
        return False
    return True


def validate_dev_test(branch_name):
    validate_branch()
    if not tag_exists(started_tag(branch_name)):
        raise GitError("Abort: Branch is missing 'started' tag.")
    if tag_exists(testing_tag(branch_name)):
        raise GitError('Abort: Testing tag already exists.')
    if not branch_name.startswith(HOTFIX) and test_in_progress():
        checkout(branch_name)
        raise GitError('Abort: Test in progress')


def test_in_progress():
    checkout(DEVELOP)
    test = get_last_commit_msg()
    return not check_test_end_keywords(test)


def check_test_end_keywords(test):
    for word in DEVELOP_END_KEYWORDS:
        if word in test:
            return True
    return False


def validate_end_dev_test():
    if not test_in_progress():
        raise GitError('Abort: There is no tests on DEVELOP')


def validate_prolong(tag_testing, tag_finished, tag_released):
    validate_branch()
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released')
    if tag_exists(tag_testing) is False and tag_exists(tag_finished) is False:
        raise GitError('Abort: Branch is already active.')


def validate_finish(tag_finished, tag_released):
    validate_branch()
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released.')
    if tag_exists(tag_finished):
        raise GitError('Abort: Branch is already finished.')


def validate_release(tag_finished, tag_released):
    if tag_exists(tag_released):
        raise GitError('Abort: Branch is already released')
    if not tag_exists(tag_finished):
        raise GitError('Abort: Branch is not finished')
    if tag_exists(approval_tag()):
        raise GitError('Abort: RELEASE branch is waiting for approval')
    if tag_exists(overall_approval_tag()):
        raise GitError('Abort: RELEASE branch is waiting for overall approval')


def validate_approve():
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command approve is allowed only on RELEASE branch')
    if tag_exists(approval_tag()) is False and tag_exists(overall_approval_tag()) is False:
        raise GitError('Abort: RELEASE branch is already approved')


def validate_redeem(branch_name):
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command redeem is allowed only on RELEASE branch')
    if not tag_exists(approval_tag()):
        raise GitError('Abort: There is nothing to redeem on RELEASE branch')
    if not tag_exists(released_tag(branch_name)):
        raise GitError('Fatal: Branch missing release tag.')


def validate_remove(branch_name):
    if get_current_branch() != RELEASE:
        raise GitError('Abort: Command remove is allowed only on RELEASE branch')
    if not get_last_commit_msg_with_substring(branch_name):
        raise GitError('Abort: There is no released feature, bugfix or hotfix named %s' % branch_name)
    if not tag_exists(released_tag(branch_name)):
        raise GitError('Fatal: Branch %s is missing release tag.' % branch_name)
    if tag_exists(approval_tag()):
        raise GitError('Abort: RELEASE branch is waiting for approval')
    if tag_exists(overall_approval_tag()):
        raise GitError('Abort: RELEASE branch is waiting for overall approval')


def validate_publish(current_branch):
    if current_branch != RELEASE and current_branch != HOTFIX:
        raise GitError('Abort: Command publish is allowed only on RELEASE and HOTFIX branches')


def validate_version_tag(tag_name):
    if tag_exists(tag_name) is False:
        raise GitError('Fatal: Version %s tag do not exists.' % tag_name)
