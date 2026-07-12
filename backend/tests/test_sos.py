"""SOS flow: activate, share location, contacts notified, cancel."""

from app.bot.router import handle_inbound
from app.enums import SOSStatus
from app.services import sos_service
from app.services.user_service import get_user_by_phone
from tests.conftest import make_inbound, register_user

PHONE = "919822000001"
CONTACT_PHONE = "919822012345"


async def setup_user_with_contact(db, wa):
    user = await register_user(db, wa, PHONE)
    await handle_inbound(db, make_inbound(phone=PHONE, text=f"CONTACT Maria {CONTACT_PHONE}"))
    wa.sent.clear()
    return await get_user_by_phone(db, PHONE)


async def test_sos_activates_and_notifies_contact(db, wa):
    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))

    sent_to = {phone for phone, _ in wa.sent}
    assert PHONE in sent_to           # confirmation to the fisherman
    assert CONTACT_PHONE in sent_to   # alert to the emergency contact

    user_msg = next(text for phone, text in wa.sent if phone == PHONE)
    assert "🚨 EMERGENCY ACTIVATED" in user_msg
    assert "Coast Guard: 1554" in user_msg
    assert "Reply CANCEL" in user_msg
    assert "does NOT replace" in user_msg  # regulatory disclaimer

    contact_msg = next(text for phone, text in wa.sent if phone == CONTACT_PHONE)
    assert "Rajesh" in contact_msg
    assert "1554" in contact_msg

    user = await get_user_by_phone(db, PHONE)
    alert = await sos_service.get_active_alert(db, user)
    assert alert is not None and alert.status == SOSStatus.ACTIVE


async def test_sos_is_idempotent(db, wa):
    user = await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))

    alerts = await sos_service.all_active_alerts(db)
    assert len(alerts) == 1  # second SOS reuses the active alert


async def test_location_share_updates_alert_and_contact(db, wa):
    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, latitude=15.1234, longitude=73.9876))

    user = await get_user_by_phone(db, PHONE)
    alert = await sos_service.get_active_alert(db, user)
    assert alert.last_latitude == 15.1234
    assert alert.last_longitude == 73.9876

    sent_to = {phone for phone, _ in wa.sent}
    assert CONTACT_PHONE in sent_to
    contact_update = next(text for phone, text in wa.sent if phone == CONTACT_PHONE)
    assert "15.12340" in contact_update  # maps link includes coordinates


async def test_location_without_sos_is_ignored(db, wa):
    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, latitude=15.1, longitude=73.9))
    assert wa.sent == []


async def test_cancel_deactivates_and_stands_down_contact(db, wa):
    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    wa.sent.clear()

    await handle_inbound(db, make_inbound(phone=PHONE, text="CANCEL"))

    user = await get_user_by_phone(db, PHONE)
    assert await sos_service.get_active_alert(db, user) is None

    user_msg = next(text for phone, text in wa.sent if phone == PHONE)
    assert "SOS deactivated" in user_msg
    contact_msg = next(text for phone, text in wa.sent if phone == CONTACT_PHONE)
    assert "cancelled" in contact_msg


async def test_cancel_without_active_sos(db, wa):
    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="CANCEL"))
    assert "No active SOS" in wa.sent[0][1]


async def test_sos_reminder_follow_up(db, wa, monkeypatch):
    from app.scheduler import sos_follow_up

    await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    await handle_inbound(db, make_inbound(phone=PHONE, latitude=15.1, longitude=73.9))
    wa.sent.clear()

    handled = await sos_follow_up()
    assert handled == 1
    sent_to = {phone for phone, _ in wa.sent}
    assert PHONE in sent_to          # reminder to keep sharing location
    assert CONTACT_PHONE in sent_to  # relayed last-known position


async def test_ops_resolve(db, wa):
    user = await setup_user_with_contact(db, wa)
    await handle_inbound(db, make_inbound(phone=PHONE, text="SOS"))
    alert = await sos_service.get_active_alert(db, user)

    resolved = await sos_service.resolve(db, alert.id, notes="ICG notified, boat towed in")
    assert resolved.status == SOSStatus.RESOLVED
    assert await sos_service.get_active_alert(db, user) is None
