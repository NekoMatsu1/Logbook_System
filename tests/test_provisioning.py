import hashlib
import json

import pytest

import server.__main__ as cli
from server.db import connect


def arguments(monkeypatch,database,output):
    monkeypatch.setattr('sys.argv',['server','provision','--database',str(database),'--computer','PC-NEW',
                                   '--output',str(output),'--server-url','https://lab.school.edu'])


@pytest.mark.parametrize('phase',['create','write'])
def test_failed_config_creation_rolls_back_pc_enrollment(tmp_path,monkeypatch,phase):
    database,output=tmp_path/'test.sqlite',tmp_path/'private/client.json'
    arguments(monkeypatch,database,output)
    def fail_create(*args,**kwargs):
        raise PermissionError('Configuration folder is not writable')
    def fail_write(value,stream,**kwargs):
        stream.write('{')
        raise OSError('Disk full')
    if phase=='create':
        monkeypatch.setattr(cli.os,'open',fail_create)
    else:
        monkeypatch.setattr(cli.json,'dump',fail_write)
    with pytest.raises(OSError):
        cli.main()
    assert not output.exists()
    with connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM computers').fetchone()[0]==0


def test_provisioning_matches_saved_token_and_never_overwrites(tmp_path,monkeypatch):
    database,output=tmp_path/'test.sqlite',tmp_path/'private/client.json'
    arguments(monkeypatch,database,output)
    cli.main()
    original=output.read_bytes()
    config=json.loads(original)
    with connect(database) as db:
        assert db.execute('SELECT token_hash FROM computers WHERE computer_id=?',('PC-NEW',)).fetchone()[0] == hashlib.sha256(config['machine_token'].encode()).hexdigest()
    assert config['simulation'] is True and config['allow_loopback_http'] is False
    with pytest.raises(SystemExit):
        cli.main()
    assert output.read_bytes()==original
    other=tmp_path/'other.json'
    arguments(monkeypatch,database,other)
    with pytest.raises(SystemExit):
        cli.main()
    assert not other.exists()
