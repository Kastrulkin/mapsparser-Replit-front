import pytest
from services import outreach_email_adapter

class Gmail:
    capabilities=[b'X-GM-EXT-1']
    def __init__(self,raw):self.raw=raw;self.stores=[]
    def list(self):return 'OK',[b'(\\Sent) "/" "[Gmail]/Sent Mail"',b'() "/" "Raschyoska/Engelsa-154/2026-10-23"']
    def select(self,folder,readonly):return 'OK',[b'1']
    def uid(self,command,*args):
        if command=='search':return 'OK',[self.raw]
        self.stores.append(args);return 'OK',[b'ok']
    def logout(self):pass

def test_gmail_label_uses_numeric_uid_not_python_bytes_representation(monkeypatch):
    gmail=Gmail(b'14327');monkeypatch.setattr(outreach_email_adapter,'_imap_connection',lambda config,timeout:gmail)
    result=outreach_email_adapter._apply_gmail_sent_label({},message_id='<approved@localos.pro>',label_name='Raschyoska/Engelsa-154/2026-10-23',timeout=12)
    assert gmail.stores==[('14327','+X-GM-LABELS','("Raschyoska/Engelsa-154/2026-10-23")')]
    assert result['status']=='labeled'

@pytest.mark.parametrize('raw',[b'123 junk',b'0',b'\xff',b'123 124'])
def test_invalid_or_ambiguous_sent_uid_never_changes_labels(monkeypatch,raw):
    gmail=Gmail(raw);monkeypatch.setattr(outreach_email_adapter,'_imap_connection',lambda config,timeout:gmail)
    with pytest.raises(outreach_email_adapter.EmailAdapterError):
        outreach_email_adapter._apply_gmail_sent_label({},message_id='<approved@localos.pro>',label_name='Raschyoska/Engelsa-154/2026-10-23',timeout=12)
    assert gmail.stores==[]
