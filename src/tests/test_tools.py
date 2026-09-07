from unittest.mock import Mock

import pytest

from platform_api.base import Platform
from platform_api.desktop import DesktopPlatform
from tools.system import flashlight


def test_flashlight_can_be_turned_on_and_off():
    platform = DesktopPlatform()
    assert platform.flashlight_enabled is False
    flashlight(platform, True)
    assert platform.flashlight_enabled is True
    flashlight(platform, True)
    assert platform.flashlight_enabled is True
    flashlight(platform, False)
    assert platform.flashlight_enabled is False


def test_desktop_instances_have_independent_state():
    first, second = DesktopPlatform(), DesktopPlatform()
    flashlight(first, True)
    assert second.flashlight_enabled is False


@pytest.mark.parametrize("enabled", [True, False])
def test_tool_delegates_to_platform(enabled):
    platform = Mock(spec=Platform)
    flashlight(platform, enabled)
    platform.flashlight.assert_called_once_with(enabled)


@pytest.mark.parametrize("enabled", ["false", "on", 0, 1, None])
def test_invalid_requests_never_reach_platform(enabled):
    platform = Mock(spec=Platform)
    with pytest.raises(TypeError, match="enabled must be a bool"):
        flashlight(platform, enabled)
    platform.flashlight.assert_not_called()


def test_platform_failure_propagates():
    platform = Mock(spec=Platform)
    platform.flashlight.side_effect = OSError("device unavailable")
    with pytest.raises(OSError, match="device unavailable"):
        flashlight(platform, True)


def test_desktop_rejects_invalid_state_without_mutation():
    platform = DesktopPlatform()
    with pytest.raises(TypeError):
        platform.flashlight("false")
    assert platform.flashlight_enabled is False
