import pytest

from deploy.configure_oracle import configure, settings


def test_oracle_config_supports_remote_pcs_without_overwriting(tmp_path):
    output = tmp_path / '.env'
    configure(output, 'lab.school.edu', '8.8.8.8', remote_clients=True)
    original = output.read_bytes()
    assert b'LOGBOOK_ALLOW_REMOTE_CLIENTS=1\n' in original
    assert b'LOGBOOK_ADMIN_ADDRESS=8.8.8.8\n' in original
    with pytest.raises(FileExistsError):
        configure(output, 'other.school.edu', '1.1.1.1', remote_clients=True)
    assert output.read_bytes() == original


@pytest.mark.parametrize('domain,ip', [
    ('https://lab.school.edu', '8.8.8.8'), ('lab.school.edu\nEXTRA=1', '8.8.8.8'),
    ('lab.school.edu', '192.168.1.2'), ('example.org', '8.8.8.8'),
    ('lab.school.edu', '0.0.0.0'), ('127.0.0.1', '8.8.8.8'),
])
def test_invalid_oracle_values_do_not_create_config(tmp_path, domain, ip):
    output = tmp_path / '.env'
    with pytest.raises(ValueError):
        configure(output, domain, ip, remote_clients=True)
    assert not output.exists()


def test_client_network_access_requires_explicit_choice():
    with pytest.raises(ValueError):
        settings('lab.school.edu', '8.8.8.8')
    with pytest.raises(ValueError):
        settings('lab.school.edu', '8.8.8.8', True, ['1.1.1.1/32'])
    assert 'LOGBOOK_LAB_NETWORKS=1.1.1.1/32\n' in settings('lab.school.edu', '8.8.8.8', lab_networks=['1.1.1.1/32'])
