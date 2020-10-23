import os
import shutil
import time

import config
import dockerapi as docker
import util
import network
import tunnel


PWD = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PLIST_PATH = '/Library/LaunchDaemons/com.zanaca.dockerdns-tunnel.plist'
KNOWN_HOSTS_FILE = f'{config.HOME_ROOT}/.ssh/known_hosts'
APP_DESTINATION = f'{config.HOME}/Applications/dockerdns-tunnel.app'


def setup(tld=config.TOP_LEVEL_DOMAIN):
    if not os.path.isdir('/etc/resolver'):
        os.mkdir('/etc/resolver')
    open('/etc/resolver/{tld}',
         'w').write(f'nameserver {docker.NETWORK_GATEWAY}')

    plist = open('src/templates/com.zanaca.dockerdns-tunnel.plist',
                 'r').read().replace('{PWD}', PWD)
    open(PLIST_PATH, 'w').write(plist)
    os.system(f'sudo launchctl load -w {PLIST_PATH} 1>/dev/null 2>/dev/null')

    output = {
        'DOCKER_CONF_FOLDER': f'{config.HOME}/Library/Containers/com.docker.docker/Data/database/com.docker.driver.amd64-linux/etc/docker'
    }

    return output


def install(tld=config.TOP_LEVEL_DOMAIN):
    print('Generating known_hosts backup for user "root", if necessary')
    if not os.path.exists(f'{config.HOME_ROOT}/.ssh'):
        os.mkdir(f'{config.HOME_ROOT}/.ssh')
        os.chmod(f'{config.HOME_ROOT}/.ssh', 700)

    if os.path.exists(KNOWN_HOSTS_FILE):
        shutil.copy2(KNOWN_HOSTS_FILE,
                     f'{config.HOME_ROOT}/.ssh/known_hosts_pre_docker-dns')

    time.sleep(3)
    port = False
    ports = docker.get_exposed_port(config.DOCKER_CONTAINER_NAME)
    if '22/tcp' in ports:
        port = int(ports['22/tcp'][0]['HostPort'])
    if not port:
        raise('Problem fetching ssh port')

    keys = os.popen(f'ssh-keyscan -p {port} 127.0.0.1').read().split("\n")
    for key in keys:
        if 'ecdsa-sha2-nistp256' in key:
            print('Adding key to known_hosts for user "root"')
            open(KNOWN_HOSTS_FILE, 'a+').write(f"\n{key}\n")

    if not os.path.exists(APP_DESTINATION):
        shutil.copytree('src/templates/dockerdns-tunnel_app', APP_DESTINATION)
    workflow = open(f'{APP_DESTINATION}/Contents/document.wflow', 'r').read()
    workflow = workflow.replace(
        '[PATH]', PWD)
    open(f'{APP_DESTINATION}/Contents/document.wflow', 'w').write(workflow)

    tunnel.connect(daemon=True)


def uninstall(tld=config.TOP_LEVEL_DOMAIN):
    if os.path.exists(f'/etc/resolver/{tld}'):
        print('Removing resolver file')
        os.unlink(f'/etc/resolver/{tld}')
    if os.path.exists(PLIST_PATH):
        print('Removing tunnel service')
        os.system(
            f'sudo launchctl unload -w {PLIST_PATH} 1>/dev/null 2>/dev/null')
        os.unlink(PLIST_PATH)
    if os.path.exists(f'{config.HOME_ROOT}/.ssh/known_hosts_pre_docker-dns'):
        print('Removing kwown_hosts backup')
        os.unlink(f'{config.HOME_ROOT}/.ssh/known_hosts_pre_docker-dns')

    if os.path.exists(APP_DESTINATION):
        print('Removing tunnel app')
        for filename in os.listdir(APP_DESTINATION):
            file_path = os.path.join(APP_DESTINATION, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))
