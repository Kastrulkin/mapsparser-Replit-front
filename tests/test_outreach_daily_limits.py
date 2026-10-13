import pytest
from services.outreach_daily_limits import sender_daily_limit, LIMITS_VERSION


@pytest.mark.parametrize('channel,expected',[('email',300),('vk',50),('telegram',50),('facebook',50)])
def test_current_owner_limits_replace_legacy_builder_defaults(channel,expected):
    assert sender_daily_limit(channel,{'daily_limit':10})==expected
    assert sender_daily_limit(channel,{})==expected


def test_reviewed_lower_channel_cap_remains_and_cannot_raise_owner_ceiling():
    assert sender_daily_limit('email',{'daily_limits_version':LIMITS_VERSION,'channel_daily_limits':{'email':25}})==25
    assert sender_daily_limit('vk',{'daily_limits_version':LIMITS_VERSION,'channel_daily_limits':{'vk':300}})==50


@pytest.mark.parametrize('value',[None,True,0,-1,'300'])
def test_invalid_versioned_caps_cannot_disable_limiting(value):
    with pytest.raises(ValueError):sender_daily_limit('email',{'daily_limits_version':LIMITS_VERSION,'channel_daily_limits':{'email':value}})


def test_unknown_channel_does_not_gain_sending_permission():
    assert sender_daily_limit('new_channel', {'daily_limit':7}) == 7
    assert sender_daily_limit('new_channel', {}) == 10


def test_author_lanes_use_same_channel_caps_without_breaking_old_review_identity():
    from services.outreach_daily_limits import author_limits_match, AUTHOR_TOTAL_LIMIT, AUTHOR_CHANNEL_LIMITS, AUTHOR_LIMITS_VERSION
    assert AUTHOR_CHANNEL_LIMITS == {'email':300,'telegram':50,'vk':50}
    assert AUTHOR_TOTAL_LIMIT == 400
    assert author_limits_match({'author_policy_version':'localos-author-daily-v2','daily_limit':200,'channel_daily_limits':{'email':150,'telegram':25,'vk':25}})
    assert author_limits_match({'author_policy_version':AUTHOR_LIMITS_VERSION,'daily_limit':400,'channel_daily_limits':AUTHOR_CHANNEL_LIMITS})
    assert not author_limits_match({'author_policy_version':'unknown','daily_limit':400,'channel_daily_limits':AUTHOR_CHANNEL_LIMITS})
