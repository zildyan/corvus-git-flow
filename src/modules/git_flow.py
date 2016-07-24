#!/usr/bin/python

from modules.git_validation import *
from modules.git_core import *
from modules.git_format import *


def start_flow_initialization(version):
    try:
        validate_initialization()
        root_branch = get_current_branch()
        set_config_options()

        for branch in MAIN_BRANCHES:
            create_new_branch(branch, root_branch)

            if branch in [PROD, RELEASE, DEVELOP]:
                squash_all_commits('Flow initialization - version %s - success' % version)

            commit_amend()

            if branch in [RELEASE, STABLE, HISTORY]:
                add_tag('%s/%s' % (branch, version))

            push_to_origin(branch, SET_UPSTREAM)
            checkout(root_branch)

        # delete_local_branch(root_branch)
        msg = ['', '  Flow initialization successfully finished.',
               '', '  Set default branch on remote repository to PROD,',
               '  and then manually delete %s' % root_branch]

        return format_rows(msg)

    except GitError as ex:
        raise ex


def create_new_bugfix_branch(branch_name):
    return create_flow_branch(branch_name, BUGFIX, STABLE)


def create_new_feature_branch(branch_name):
    return create_flow_branch(branch_name, FEATURE, STABLE)


def create_new_hotfix_branch(branch_name):
    return create_flow_branch(branch_name, HOTFIX, PROD)


def create_new_support_branch(branch_name):
    return create_flow_branch(branch_name, SUPPORT)


def create_flow_branch(branch_name, branch_type, main_branch=None):
    if main_branch is None:
        if branch_name.startswith(SUPPORT):
            main_branch = get_current_branch()

    branch_full_name = '%s/%s' % (branch_type, branch_name)
    create_new_branch(branch_full_name, main_branch)
    commit_amend()
    add_tag(started_tag(branch_name))
    push_to_origin(branch_full_name, SET_UPSTREAM)
    return format_blanks('Successfully created %s branch' % branch_full_name)


def dev_test():
    current_branch = get_current_branch()
    validate_dev_test(current_branch)
    end_dev_test_if_hotfix(current_branch)

    test_name = get_test_name(current_branch)
    tag_started = started_tag(current_branch)
    tag_testing = testing_tag(current_branch)

    checkout(current_branch)
    add_tag(tag_testing)
    patch_name = format_patch_name(current_branch, 'test')
    create_patch(tag_started, tag_testing, patch_name)

    checkout(DEVELOP)
    apply_patch(patch_name)
    delete_patch(patch_name)
    commit_all_changes(test_name)
    push_to_origin(DEVELOP)

    checkout(current_branch)
    return format_blanks('Test applied on DEVELOP.')


def end_dev_test_if_hotfix(current_branch):
    if current_branch.startswith(HOTFIX) and test_in_progress():
        prolong_testing_branch()


def get_test_name(branch_name):
    number = get_test_number(branch_name)
    test_name = '%s/test#%s' % (branch_name, str(number))
    return test_name


def get_test_number(branch_name):
    checkout(DEVELOP)
    test = get_last_commit_msg_with_substring(branch_name)
    if test == '':
        return '1'

    test_num = test.split('#')[1]
    if check_test_end_keywords(test_num) is True:
        test_num = test_num.split('/')[0]

    return int(test_num) + 1


def prolong(with_force=False):
    current_branch = get_current_branch()
    tag_testing = testing_tag(current_branch)
    tag_finished = finished_tag(current_branch)
    tag_released = released_tag(current_branch)

    validate_prolong(tag_testing, tag_finished, tag_released)

    if tag_exists(tag_finished):
        remove_tag(tag_finished)

    elif tag_exists(tag_testing) and test_in_progress():
        terminate_test(current_branch, with_force)
        remove_tag(tag_testing)

    checkout(current_branch)
    return format_blanks('Branch successfully prolonged.')


def terminate_test(branch_name, with_force=False):
    if branch_name.startswith(HOTFIX) or with_force:
        end_dev_test('forced_down')
    else:
        end_dev_test('failed')


def end_dev_test(reason_of_shutting_down):
    checkout(DEVELOP)
    validate_end_dev_test()

    name_of_tested_branch = get_last_commit_msg().rstrip()
    commit_msg = '%s/%s' % (name_of_tested_branch, reason_of_shutting_down)
    revert_commit()
    commit_all_changes(commit_msg)
    push_to_origin(DEVELOP)


def finish():
    current_branch = get_current_branch()
    tag_finished = finished_tag(current_branch)
    tag_released = released_tag(current_branch)
    validate_finish(tag_finished, tag_released)

    end_test_with_success(current_branch)
    checkout(current_branch)
    add_tag(tag_finished)
    return format_blanks('Branch successfully finished.')


def end_test_with_success(branch_name):
    tag_testing = testing_tag(branch_name)
    if tag_exists(tag_testing) and test_in_progress():
        remove_tag(tag_testing)
        end_dev_test('success')


def release():
    current_branch = get_current_branch()
    tag_finished = finished_tag(current_branch)
    tag_released = released_tag(current_branch)

    validate_release(tag_finished, tag_released)

    patch_name = format_patch_name(current_branch, 'release')
    create_patch(started_tag(current_branch), tag_finished, patch_name)

    checkout(RELEASE)
    apply_patch(patch_name)
    delete_patch(patch_name)
    commit_all_changes('%s' % current_branch)
    add_tag(approval_tag())
    push_to_origin(RELEASE)

    checkout(current_branch)
    remove_tag(tag_finished)
    add_tag(tag_released)
    return format_blanks('Branch successfully released.')


def approve():
    validate_approve()
    if tag_exists(approval_tag()):
        remove_tag(approval_tag())
    elif tag_exists(overall_approval_tag()):
        remove_tag(overall_approval_tag())
    return format_blanks('Successfully approved.')


def redeem():
    branch_name = get_last_commit_msg().rstrip()
    validate_redeem(branch_name)
    checkout(branch_name)
    validate_branch()

    checkout(branch_name)
    remove_tag(released_tag(branch_name))
    add_tag(finished_tag(branch_name))

    checkout(RELEASE)
    remove_tag(approval_tag())
    hard_reset_to_previous_commit()
    push_to_origin(RELEASE)
    return format_blanks('%s needs to redeem itself.' % branch_name)


def remove(branch_name):
    validate_remove(branch_name)
    remove_tag(released_tag(branch_name))

    commit_sha = get_sha_of_commit_with_msg(branch_name)
    revert_commit(commit_sha)
    commit_all_changes('REMOVED/%s' % branch_name)
    add_tag(overall_approval_tag())
    push_to_origin(RELEASE)

    checkout(branch_name)
    add_tag(finished_tag(branch_name))
    return format_blanks('Branch %s successfully removed from RELEASE' % branch_name)


def publish(version):
    current_branch = get_current_branch()
    validate_publish(current_branch)

    if test_in_progress():
        prolong_testing_branch()
        checkout(current_branch)

    tag_started = started_tag(current_branch)
    tag_finished = finished_tag(current_branch)
    patch_name = format_patch_name(current_branch, 'release')
    create_patch(tag_started, tag_finished, patch_name)

    checkout(DEVELOP)
    apply_patch(patch_name)
    commit('%s' % version)

    checkout(RELEASE)
    add_tag('RELEASE/%s' % version)

    checkout(PROD)
    apply_patch(patch_name)
    commit('%s' % version)

    # TODO stable
    push_to_origin(DEVELOP)
    push_to_origin(STABLE)
    push_to_origin(PROD)

    return ''


def prolong_testing_branch():
    checkout(DEVELOP)
    branch_name = get_last_test_branch_name()
    checkout(branch_name)
    validate_branch()
    prolong(True)


def get_last_test_branch_name():
    return get_last_commit_msg().split('/test')[0]


def in_version(version=None):
    if version is None:
        to_tag = 'head'
        from_tag = execute('git describe --abbrev=0 --match=RELEASE/*', WITH_RESPONSE)
    else:
        to_tag = 'RELEASE/%s' % version
        validate_version_tag(to_tag)
        from_tag = execute('git describe --abbrev=0 --match=RELEASE/* %s~1' % to_tag, WITH_RESPONSE)

    validate_version_tag(from_tag)
    return get_version_upgrades(from_tag, to_tag)


def get_version_upgrades(from_tag, to_tag):
    all_upgrades = execute('git log --pretty=%B ' + to_tag + '...' + from_tag, WITH_RESPONSE)
    all_upgrades_splitted = all_upgrades.splitlines()

    if all_upgrades is None or len(all_upgrades_splitted) == 0:
        return format_blanks('None of upgrades found.')

    removed_upgrades = get_removed_upgrades(all_upgrades_splitted)

    if len(removed_upgrades) != 0:
        upgrades = get_upgrades(all_upgrades_splitted, removed_upgrades)
    else:
        upgrades = all_upgrades_splitted

    return '\n' + format_lines(upgrades)


def get_removed_upgrades(all_upgrades_splitted):
    removed_upgrades = []
    for upgrade in all_upgrades_splitted:
        if 'REMOVED' in upgrade:
            removed_upgrades.append(upgrade)
            removed_upgrades.append(upgrade.split('REMOVED/')[1])
    return removed_upgrades


def get_upgrades(all_upgrades_splitted, removed_upgrades):
    upgrades = []
    for upgrade in all_upgrades_splitted:
        if upgrade not in removed_upgrades:
            upgrades.append(upgrade)
    return upgrades


def commit_with_prefix(commit_msg):
    validate_branch()
    commit_msg = format_commit_msg(get_current_branch(), commit_msg)
    commit(commit_msg)
