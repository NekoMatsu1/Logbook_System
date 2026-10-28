# Set up Oracle Cloud

No Oracle account or server has been created yet. Start with step 1.

## 1. Create your account

Open [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) and choose the free signup option.

Enter your own name, email, phone, address, and card details on Oracle's website. Complete its checks yourself. Do not send passwords, card details, or private SSH keys in chat.

Stay on the free account. Do not upgrade to Pay As You Go. Trial credit expires; use resources marked **Always Free eligible** within your account's current limits. If the console shows a charge or no free capacity, stop. See [Oracle's signup guide](https://docs.oracle.com/en/learn/cloud_free_tier/index.html) and [free-tier rules](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

## 2. Create the server

In the Oracle console, open **Compute > Instances > Create instance**.

- Name: `lab-logbook`.
- Image: Canonical Ubuntu 24.04 LTS.
- Shape and boot disk: choose settings shown as Always Free eligible, within the limits shown for your account. Check existing usage too.
- Network: a public subnet with an internet gateway and a public IPv4 address.
- SSH: save the private key on your admin PC. Keep a backup; never upload it to GitHub.

Check the cost summary before you create the instance. Wait until it says **Running**, then note its public IP. Free capacity may be unavailable, and idle free VMs may be reclaimed.

## 3. Set the network rules

Find the admin PC's public IPv4 in your router or network provider's settings. A `192.168.x.x` or `10.x.x.x` address is private and will not work here. If your public IP changes, the allowlist must change too.

In the instance's VCN security list or network security group, allow these **stateful inbound TCP** rules:

| Port | Source | Use |
| --- | --- | --- |
| 22 | Your admin public IPv4 with `/32` | SSH |
| 80 | `0.0.0.0/0` | HTTPS certificate checks and redirect |
| 443 | `0.0.0.0/0` | Student API and restricted dashboard |

Keep source ports set to all. Replace any existing broad SSH rule with the admin `/32` rule, then verify a new SSH connection works. Do not open port 5000 or 2019. Keep Oracle's required service and outbound rules. See [Oracle security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm).

## 4. Get a hostname

Use a hostname you control. Set its DNS A record to the VM's public IPv4. A free DNS name is fine if you can manage its record. Do not add an AAAA record unless IPv6 is configured. Point DNS directly at the VM; do not add a proxy in front.

You will need these values: VM public IP, hostname, admin public IPv4, and the local path to your SSH key.

## 5. Upload this project's server package

On the development PC, from the project folder:

```powershell
.\.venv\bin\python.exe deploy/package.py
ssh -i "C:\path\to\your-key" ubuntu@VM_PUBLIC_IP
```

Check the SSH host fingerprint against the VM's trusted console information before accepting it. In a second local terminal, upload the archive:

```powershell
scp -i "C:\path\to\your-key" .tools/logbook-deploy.zip ubuntu@VM_PUBLIC_IP:~/logbook-deploy.zip
```

On the VM:

```bash
sudo apt-get update
sudo apt-get install -y unzip python3 docker.io docker-compose-v2
sudo systemctl enable --now docker
mkdir -p ~/lab-logbook
cd ~/lab-logbook
unzip -n ~/logbook-deploy.zip
cd deploy
python3 configure_oracle.py --domain YOUR_HOSTNAME --admin-ip YOUR_ADMIN_PUBLIC_IPV4 --remote-clients
python3 prepare.py
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=50 app edge
```

Replace the uppercase values. The setup command refuses to replace an existing `.env`. `--remote-clients` allows provisioned PCs from different networks. For one fixed lab network, replace it with `--lab-network YOUR_LAB_PUBLIC_IPV4/32`. Each PC still needs its own private machine credential.

Ubuntu provides [Docker Compose v2](https://packages.ubuntu.com/noble/docker-compose-v2). On a fresh VM, extract once into a new folder. For later updates, back up the database first and follow the full deployment guide.

The VM's own firewall must allow TCP 80 and 443 too. Inspect `sudo iptables -S INPUT`. If those ports are blocked by the stock rules, add only these rules before its reject rule:

```bash
sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT || sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
sudo iptables -C INPUT -p tcp --dport 443 -j ACCEPT || sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Use those commands only on the Oracle VM. Keep its other firewall rules. If `netfilter-persistent` is missing or the VM uses another firewall manager, use that manager to save equivalent rules. Confirm the rules survive a reboot. See [Ubuntu firewall documentation](https://documentation.ubuntu.com/security/security-features/network/firewall/).

## 6. Check it and connect a PC

From the allowed admin network, open `https://YOUR_HOSTNAME/admin/overview`. From another network, that page must return 403. A request without a PC token to `https://YOUR_HOSTNAME/api/students/unknown` must return 401.

Use the [full server guide](README.md#connect-pcs-from-different-locations) to provision each PC and copy its JSON privately. Test with simulation enabled. Back up and restore the database before keeping real records.

The dashboard allowlist identifies a public IP, not one device. Other devices sharing that public IP can reach it. Do not use this mode on a shared or untrusted admin network. HTTPS and restrictions must be checked on the real VM; local tests do not prove the server is deployed.
