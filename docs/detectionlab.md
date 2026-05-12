# DetectionLab Directory Documentation

## Overview

The detectionlab directory contains Vagrant configuration for setting up a comprehensive Windows detection laboratory environment. This lab creates a realistic Windows domain infrastructure that generates authentic security logs and events for HIKARI competitions, providing the source data that teams analyze in Kibana.

## Directory Structure

```
detectionlab/
└── Vagrantfile          # Complete infrastructure-as-code configuration
```

## Laboratory Architecture

### Network Configuration

**Network Segment**: `192.168.56.0/24`
- **Gateway**: `192.168.56.1` (VirtualBox host)
- **DNS**: `192.168.56.102` (Domain Controller)
- **Subnet Mask**: `255.255.255.0`

### Virtual Machines

**1. Logger (`logger`) - Ubuntu 20.04**
- **IP Address**: `192.168.56.105`
- **Role**: Centralized log collection and processing
- **CPU**: 1 core
- **Memory**: 2GB
- **Storage**: 25GB

**2. Domain Controller (`dc`) - Windows Server 2016**
- **IP Address**: `192.168.56.102`
- **Role**: Active Directory domain controller
- **Domain**: `windomain.local`
- **CPU**: 2 cores
- **Memory**: 3GB
- **Storage**: 65GB

**3. Windows Event Forwarding (`wef`) - Windows Server 2016**
- **IP Address**: `192.168.56.103`
- **Role**: Centralized Windows event collection
- **CPU**: 1 core
- **Memory**: 2GB
- **Storage**: 65GB

**4. Windows Client (`win10`) - Windows 10**
- **IP Address**: `192.168.56.104`
- **Role**: User workstation for attack simulation
- **CPU**: 1 core
- **Memory**: 2GB
- **Storage**: 65GB

## System Components

### 1. Logger System (Ubuntu 20.04)

**Purpose**: Centralized log collection and SIEM capabilities

**Installed Components**:
```bash
# Security monitoring tools
- Suricata IDS/IPS
- Zeek network analysis
- Osquery endpoint monitoring
- Velociraptor incident response

# Log processing
- Rsyslog for system logs
- Filebeat for log shipping
- Kafka for event streaming

# Analysis tools
- Jupyter notebooks
- Python analysis libraries
- NetworkX for graph analysis
```

**Configuration**:
```ruby
logger.vm.provision "shell", inline: <<-SHELL
  # Update system
  apt-get update && apt-get upgrade -y
  
  # Install security tools
  apt-get install -y suricata zeek osquery
  
  # Configure Suricata
  suricata-update
  systemctl enable suricata
  
  # Setup Zeek
  /opt/zeek/bin/zeekctl deploy
  
  # Configure Osquery
  osqueryctl start
SHELL
```

### 2. Domain Controller (Windows Server 2016)

**Purpose**: Active Directory services and domain management

**Domain Configuration**:
```powershell
# Domain setup
$DomainName = "windomain.local"
$SafeModePassword = ConvertTo-SecureString "P@ssw0rd123" -AsPlainText -Force

# Install AD DS role
Install-WindowsFeature -Name AD-Domain-Services -IncludeManagementTools

# Promote to domain controller
Install-ADDSForest -DomainName $DomainName -SafeModeAdministratorPassword $SafeModePassword -Force
```

**Security Policies**:
```ruby
dc.vm.provision "shell", inline: <<-SHELL
  # Enable advanced audit policies
  auditpol /set /subcategory:"Logon" /success:enable /failure:enable
  auditpol /set /subcategory:"Process Creation" /success:enable
  auditpol /set /subcategory:"Registry" /success:enable
  
  # Configure PowerShell logging
  reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ModuleLogging" /v EnableModuleLogging /t REG_DWORD /d 1
  reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging" /v EnableScriptBlockLogging /t REG_DWORD /d 1
SHELL
```

### 3. Windows Event Forwarding (WEF) Server

**Purpose**: Centralized Windows event collection

**WEF Configuration**:
```powershell
# Configure WEF subscription
$SubscriptionXML = @"
<Subscription xmlns="http://schemas.microsoft.com/2006/03/windows/events/subscription">
  <SubscriptionId>Security-Logs</SubscriptionId>
  <SubscriptionType>SourceInitiated</SubscriptionType>
  <Description>Security event collection</Description>
  <Query>
    <![CDATA[
      <QueryList>
        <Query Id="0">
          <Select Path="Security">*[System[(EventID=4624 or EventID=4625 or EventID=4688)]]</Select>
          <Select Path="System">*[System[(EventID=7045)]]</Select>
        </Query>
      </QueryList>
    ]]>
  </Query>
</Subscription>
"@

# Create subscription
wecutil cs $SubscriptionXML
```

**Event Forwarding Setup**:
```ruby
wef.vm.provision "shell", inline: <<-SHELL
  # Enable WinRM
  winrm qc -force
  
  # Configure WEF service
  wecutil qc -quiet
  
  # Set up event subscriptions
  wecutil cs Security-Events.xml
SHELL
```

### 4. Windows 10 Client

**Purpose**: User workstation for attack simulation and monitoring

**Security Configuration**:
```powershell
# Enable Windows Defender logging
Set-MpPreference -DisableRealtimeMonitoring $false
Set-MpPreference -DisableIOAVProtection $false
Set-MpPreference -DisableScriptScanning $false

# Configure Sysmon
sysmon -accepteula -i sysmon-config.xml

# Enable PowerShell logging
$RegPath = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell"
New-ItemProperty -Path "$RegPath\\ModuleLogging" -Name "EnableModuleLogging" -Value 1 -PropertyType DWORD
New-ItemProperty -Path "$RegPath\\ScriptBlockLogging" -Name "EnableScriptBlockLogging" -Value 1 -PropertyType DWORD
```

## Security Tools Integration

### 1. Osquery Deployment

**Configuration** (`osquery.conf`):
```json
{
  "options": {
    "config_plugin": "filesystem",
    "logger_plugin": "filesystem",
    "log_result_events": "true",
    "schedule_splay_percent": "10",
    "worker_threads": "2"
  },
  "schedule": {
    "network_connections": {
      "query": "SELECT * FROM process_open_sockets WHERE remote_address != '127.0.0.1' AND remote_address != '::1';",
      "interval": 30
    },
    "process_events": {
      "query": "SELECT * FROM processes WHERE state = 'R';",
      "interval": 60
    },
    "file_events": {
      "query": "SELECT * FROM file_events WHERE category = 'created' OR category = 'modified';",
      "interval": 30
    }
  }
}
```

### 2. Velociraptor Configuration

**Server Configuration**:
```yaml
version: 1.0.0
Client:
  server_urls:
    - https://192.168.56.105:8000/
  ca_certificate: |
    -----BEGIN CERTIFICATE-----
    [Certificate content]
    -----END CERTIFICATE-----
  
logging:
  output_directory: /var/log/velociraptor
  separate_logs_per_client: true
  
monitoring:
  bind_address: 0.0.0.0
  bind_port: 8003
```

### 3. Suricata IDS Configuration

**Rules Configuration** (`suricata.yaml`):
```yaml
vars:
  address-groups:
    HOME_NET: "[192.168.56.0/24]"
    EXTERNAL_NET: "!$HOME_NET"
    
  port-groups:
    HTTP_PORTS: "80,443"
    SHELLCODE_PORTS: "!80"

rule-files:
  - suricata.rules
  - emerging-threats.rules
  - local.rules

outputs:
  - eve-log:
      enabled: yes
      filetype: regular
      filename: eve.json
      types:
        - alert
        - http
        - dns
        - tls
        - files
        - smtp
```

## Attack Simulation Tools

### 1. Red Team Tools

**Installed Tools**:
```powershell
# Download and install penetration testing tools
Invoke-WebRequest -Uri "https://github.com/PowerShellMafia/PowerSploit/archive/master.zip" -OutFile "PowerSploit.zip"
Expand-Archive "PowerSploit.zip" -DestinationPath "C:\\Tools\\"

# Mimikatz for credential extraction
Invoke-WebRequest -Uri "https://github.com/gentilkiwi/mimikatz/releases/latest/download/mimikatz_trunk.zip" -OutFile "mimikatz.zip"
Expand-Archive "mimikatz.zip" -DestinationPath "C:\\Tools\\mimikatz\\"

# BloodHound for AD enumeration
Invoke-WebRequest -Uri "https://github.com/BloodHoundAD/BloodHound/releases/latest/download/BloodHound-win32-x64.zip" -OutFile "BloodHound.zip"
```

### 2. Malware Simulation

**Simulated Malware Behavior**:
```powershell
# Process injection simulation
$ProcessName = "notepad.exe"
Start-Process $ProcessName
$Process = Get-Process $ProcessName
$ProcessId = $Process.Id

# Registry persistence simulation
$RegPath = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
Set-ItemProperty -Path $RegPath -Name "WindowsUpdate" -Value "C:\\Temp\\malware.exe"

# Network communication simulation
$C2Server = "192.168.56.200"
$Port = 443
Test-NetConnection -ComputerName $C2Server -Port $Port
```

## Log Generation and Collection

### 1. Windows Event Log Configuration

**Event Categories**:
- **Security Events**: Authentication, privilege usage, object access
- **System Events**: Service control, system state changes
- **Application Events**: Application errors and warnings
- **PowerShell Events**: Command execution and script blocks
- **Sysmon Events**: Detailed process and network monitoring

**Event Forwarding Rules**:
```xml
<Subscription>
  <SubscriptionId>HIKARI-Security-Events</SubscriptionId>
  <SubscriptionType>SourceInitiated</SubscriptionType>
  <Query>
    <![CDATA[
      <QueryList>
        <Query Id="0" Path="Security">
          <Select>*[System[(EventID=4624 or EventID=4625 or EventID=4688 or EventID=4689)]]</Select>
        </Query>
        <Query Id="1" Path="Microsoft-Windows-Sysmon/Operational">
          <Select>*[System[(EventID=1 or EventID=3 or EventID=11 or EventID=22)]]</Select>
        </Query>
      </QueryList>
    ]]>
  </Query>
</Subscription>
```

### 2. Network Traffic Capture

**Zeek Network Analysis**:
```bash
# Zeek configuration for network monitoring
@load base/protocols/http
@load base/protocols/dns
@load base/protocols/ssl
@load base/protocols/smtp

# Custom scripts for malware detection
@load ./local/malware-detection.zeek

# Output to JSON format
redef LogAscii::json_timestamps = JSON::TS_ISO8601;
redef LogAscii::use_json = T;
```

## Integration with HIKARI Platform

### 1. Log Export to HIKARI

**Log Shipping Configuration**:
```bash
# Filebeat configuration for log shipping
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/suricata/eve.json
    - /var/log/zeek/*.log
    - /var/log/osquery/osqueryd.results.log
  fields:
    logtype: network
    
- type: winlogbeat
  enabled: true
  event_logs:
    - name: Security
    - name: System
    - name: Application
    - name: Microsoft-Windows-Sysmon/Operational
  fields:
    logtype: windows

output.kafka:
  hosts: ["192.168.56.1:9092"]
  topic: "competition1"
  compression: "gzip"
```

### 2. Data Processing Pipeline

**Logstash Configuration**:
```ruby
input {
  kafka {
    bootstrap_servers => "localhost:9092"
    topics => ["competition1"]
    codec => "json"
  }
}

filter {
  if [logtype] == "network" {
    mutate {
      add_field => { "data_source" => "detectionlab" }
    }
  }
  
  if [logtype] == "windows" {
    mutate {
      add_field => { "data_source" => "detectionlab" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "detectionlab-%{+YYYY.MM.dd}"
  }
}
```

## Deployment Instructions

### 1. Prerequisites

**Software Requirements**:
- VirtualBox 6.1+
- Vagrant 2.2+
- 16GB+ RAM
- 200GB+ available disk space

**Network Requirements**:
- Host-only network adapter
- Internet connectivity for downloads

### 2. Deployment Steps

**1. Clone Repository**:
```bash
git clone https://github.com/your-repo/hikari.git
cd hikari/detectionlab
```

**2. Start Laboratory**:
```bash
# Start all VMs
vagrant up

# Or start individual VMs
vagrant up logger
vagrant up dc
vagrant up wef
vagrant up win10
```

**3. Verify Deployment**:
```bash
# Check VM status
vagrant status

# Access VMs
vagrant ssh logger
vagrant rdp win10
```

### 3. Post-Deployment Configuration

**Domain Join**:
```powershell
# Join Windows machines to domain
Add-Computer -DomainName "windomain.local" -Credential (Get-Credential)
Restart-Computer
```

**Service Verification**:
```bash
# Verify services on logger
systemctl status suricata
systemctl status zeek
systemctl status osquery
```

## Use Cases

### 1. Competition Log Generation

**Scenario**: Generate realistic attack logs for HIKARI competitions
**Process**: 
1. Deploy detection lab
2. Execute simulated attacks
3. Collect generated logs
4. Process and anonymize data
5. Upload to HIKARI platform

### 2. Security Research

**Scenario**: Test detection capabilities and develop new rules
**Process**:
1. Deploy controlled environment
2. Execute known attack techniques
3. Analyze detection coverage
4. Develop new detection rules
5. Validate rule effectiveness

### 3. Training and Education

**Scenario**: Hands-on security training for analysts
**Process**:
1. Provide students with lab access
2. Guide through attack simulation
3. Demonstrate log analysis techniques
4. Practice incident response procedures
5. Validate learning outcomes

## Security Considerations

### 1. Isolation

**Network Isolation**:
- Isolated virtual network
- No direct internet access for Windows VMs
- Controlled outbound connections

**System Isolation**:
- Dedicated virtual machines
- Snapshot capability for reset
- No sensitive data exposure

### 2. Monitoring

**Security Monitoring**:
- Comprehensive logging enabled
- Real-time event processing
- Anomaly detection capabilities
- Incident response readiness

This DetectionLab provides a comprehensive Windows domain environment that generates realistic security logs and events for HIKARI competitions, creating authentic source data for Blue Team training and analysis scenarios.