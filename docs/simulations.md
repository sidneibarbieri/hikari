# Simulations Directory Documentation

## Overview

The simulations directory contains simulation configurations, test scenarios, and competition templates for HIKARI Blue Team training competitions. These materials define competition structures, participant arrangements, and progressive challenge sequences focused on Windows security forensics.

## Directory Structure

```
simulations/
├── Competição Simulada          # Competition configuration file
├── data.zip                     # Simulation data archive
└── dummy_event.zip             # Sample event data
```

## Competition Configuration

### Simulated Competition Setup (`Competição Simulada`)

**Participants**: 8 competitors organized into 4 teams
- **Team Alpha**: Alice, Bob
- **Team Beta**: Carl, Donald  
- **Team Gamma**: Ernest, Frederich
- **Team Delta**: Goldbach, Hilbert

**Challenge Structure**: 10 interconnected challenges with dependencies
```
Challenge 1 (Initial) → Challenge 2 → Challenge 3 → ... → Challenge 10 (Final)
```

**Competition Theme**: Windows Security Forensics and Incident Response

### Challenge Progression System

**Dependency Chain**:
- Each challenge depends on the previous one being solved
- Log injection occurs when ANY team solves a prerequisite challenge
- Progressive difficulty increases analytical complexity
- Teams that solve challenges faster analyze fewer total logs

**Challenge Types**:
1. **Network Analysis**: Suspicious IP identification
2. **File System Forensics**: Modified system files detection
3. **Malware Analysis**: Malicious executable identification
4. **Process Monitoring**: Suspicious process behavior
5. **Registry Analysis**: System modification detection
6. **Network Traffic**: C2 communication patterns
7. **Persistence Mechanisms**: Autostart location analysis
8. **Lateral Movement**: Network reconnaissance detection
9. **Data Exfiltration**: Data theft indicators
10. **Attribution**: Attack campaign correlation

## Challenge Scenarios

### Challenge 1: Initial Compromise
**Objective**: Identify initial attack vector
**Log Sources**: Network logs, DNS queries, HTTP traffic
**Flag Format**: `HIKARI{suspicious_ip_address}`
**Example**: `HIKARI{203.0.113.15}`

**Sample Log Entry**:
```json
{
  "timestamp": "2025-03-25T09:00:00Z",
  "event_type": "network_connection",
  "source_ip": "192.168.1.45",
  "destination_ip": "203.0.113.15",
  "port": 443,
  "protocol": "HTTPS",
  "process": "chrome.exe",
  "user": "DOMAIN\\victim",
  "flag_indicator": "suspicious_c2_domain"
}
```

### Challenge 2: Malware Deployment
**Objective**: Find dropped malware executable
**Log Sources**: File system logs, process creation
**Flag Format**: `HIKARI{malware_filename}`
**Example**: `HIKARI{trojan.exe}`

**Sample Log Entry**:
```json
{
  "timestamp": "2025-03-25T09:05:00Z",
  "event_type": "file_creation",
  "file_path": "C:\\Users\\victim\\AppData\\Local\\Temp\\trojan.exe",
  "process": "powershell.exe",
  "parent_process": "chrome.exe",
  "file_size": 2048576,
  "file_hash": "a1b2c3d4e5f6...",
  "flag_indicator": "malware_dropped"
}
```

### Challenge 3: Persistence Establishment
**Objective**: Identify persistence mechanism
**Log Sources**: Registry modifications, scheduled tasks
**Flag Format**: `HIKARI{persistence_location}`
**Example**: `HIKARI{HKCU_Run_key}`

**Sample Log Entry**:
```json
{
  "timestamp": "2025-03-25T09:10:00Z",
  "event_type": "registry_modification",
  "registry_key": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
  "registry_value": "WindowsUpdate",
  "registry_data": "C:\\Users\\victim\\AppData\\Local\\Temp\\trojan.exe",
  "process": "trojan.exe",
  "flag_indicator": "persistence_established"
}
```

### Challenge 4: Credential Harvesting
**Objective**: Detect credential theft attempts
**Log Sources**: Process monitoring, memory access
**Flag Format**: `HIKARI{credential_tool}`
**Example**: `HIKARI{mimikatz}`

### Challenge 5: Lateral Movement
**Objective**: Identify lateral movement techniques
**Log Sources**: Network logs, authentication events
**Flag Format**: `HIKARI{target_system}`
**Example**: `HIKARI{dc01.domain.local}`

### Challenge 6: Data Discovery
**Objective**: Find data enumeration activities
**Log Sources**: File access logs, directory listings
**Flag Format**: `HIKARI{target_directory}`
**Example**: `HIKARI{C:\\Confidential\\}`

### Challenge 7: Data Staging
**Objective**: Identify data collection staging
**Log Sources**: File operations, compression tools
**Flag Format**: `HIKARI{staging_location}`
**Example**: `HIKARI{C:\\temp\\data.zip}`

### Challenge 8: Command and Control
**Objective**: Detect C2 communication patterns
**Log Sources**: Network traffic, DNS queries
**Flag Format**: `HIKARI{c2_domain}`
**Example**: `HIKARI{evil.malware.com}`

### Challenge 9: Data Exfiltration
**Objective**: Identify data theft methods
**Log Sources**: Network uploads, cloud storage
**Flag Format**: `HIKARI{exfil_method}`
**Example**: `HIKARI{dropbox_upload}`

### Challenge 10: Attribution
**Objective**: Correlate attack to known threat group
**Log Sources**: TTPs, IOCs, campaign indicators
**Flag Format**: `HIKARI{threat_group}`
**Example**: `HIKARI{APT29}`

## Data Archives

### Simulation Data (`data.zip`)

**Contents**:
- Complete log datasets for all 10 challenges
- Realistic Windows security event logs
- Network traffic captures
- File system modification records
- Registry change notifications
- Process execution logs

**Data Volume**: Approximately 1GB of compressed logs
**Format**: JSON with standardized schema
**Time Span**: 24-hour attack simulation

### Dummy Event Data (`dummy_event.zip`)

**Contents**:
- Sample event structures
- Template log entries
- Testing data for platform validation
- Minimal dataset for development

**Purpose**: Platform testing and development validation

## Configuration Schema

### Competition Configuration Format

```yaml
competition:
  name: "Windows Forensics Challenge"
  duration: "8 hours"
  max_teams: 4
  team_size: 2
  
teams:
  - name: "Alpha"
    members: ["Alice", "Bob"]
    kibana_space: "team-alpha"
    
  - name: "Beta"
    members: ["Carl", "Donald"]
    kibana_space: "team-beta"

challenges:
  - id: 1
    name: "Initial Compromise"
    depends_on: null
    logs_file: "challenge01.json"
    flag: "HIKARI{203.0.113.15}"
    
  - id: 2
    name: "Malware Deployment"
    depends_on: 1
    logs_file: "challenge02.json"
    flag: "HIKARI{trojan.exe}"
```

### Log Entry Schema

```json
{
  "timestamp": "ISO 8601 timestamp",
  "event_type": "network_connection|file_creation|process_execution|registry_modification",
  "source_ip": "IP address",
  "destination_ip": "IP address",
  "port": "port number",
  "protocol": "protocol name",
  "process": "process name",
  "parent_process": "parent process name",
  "user": "DOMAIN\\username",
  "file_path": "full file path",
  "file_size": "file size in bytes",
  "file_hash": "SHA256 hash",
  "registry_key": "registry key path",
  "registry_value": "registry value name",
  "registry_data": "registry value data",
  "command_line": "full command line",
  "flag_indicator": "hint for flag location",
  "severity": "low|medium|high|critical",
  "confidence": "confidence level 0-100"
}
```

## Usage in HIKARI Platform

### Competition Setup

1. **Team Creation**: Create teams in CTFd interface
2. **Challenge Upload**: Upload challenges with dependency chain
3. **Log Preparation**: Extract and prepare log files from archives
4. **Kibana Configuration**: Setup team-specific spaces
5. **Competition Start**: Activate initial challenges

### Progressive Log Injection

```python
# Simplified workflow
def handle_challenge_solved(challenge_id, team_id):
    # Find dependent challenges
    dependent_challenges = get_dependent_challenges(challenge_id)
    
    for dep_challenge in dependent_challenges:
        if not dep_challenge.logs_activated:
            # Inject logs for dependent challenge
            inject_logs_to_kafka(dep_challenge.logs_file)
            dep_challenge.logs_activated = True
            
            # Notify all teams
            send_notification(f"New logs available for Challenge {dep_challenge.id}")
```

### Monitoring and Analytics

**Real-time Metrics**:
- Challenge completion rates
- Team progress comparison
- Log analysis efficiency
- Platform performance

**Post-Competition Analysis**:
- Team performance comparison
- Challenge difficulty assessment
- Platform usage patterns
- Educational outcome measurement

## Educational Objectives

### Blue Team Skills Development

**Technical Skills**:
- Log analysis and correlation
- Incident response procedures
- Threat hunting techniques
- Digital forensics methods

**Analytical Skills**:
- Pattern recognition
- Timeline reconstruction
- Evidence correlation
- Threat attribution

**Tools Proficiency**:
- Elasticsearch/Kibana usage
- Query language mastery
- Visualization creation
- Data filtering techniques

### Learning Outcomes

**Immediate**: Hands-on experience with security tools
**Intermediate**: Incident response methodology
**Advanced**: Threat intelligence correlation
**Expert**: Campaign attribution and prediction

## Customization Options

### Difficulty Scaling

**Beginner Level**:
- Clear indicators in logs
- Straightforward flag formats
- Guided analysis steps
- Reduced log volume

**Intermediate Level**:
- Mixed signal-to-noise ratio
- Complex flag formats
- Multiple analysis paths
- Moderate log volume

**Advanced Level**:
- High noise-to-signal ratio
- Obfuscated indicators
- Multiple valid interpretations
- Large log volumes

### Theme Variations

**APT Campaigns**: Nation-state attack simulation
**Ransomware**: Crypto-malware incident response
**Insider Threats**: Malicious employee detection
**Supply Chain**: Third-party compromise analysis

This simulations directory provides comprehensive templates and configurations for creating realistic Blue Team training scenarios, enabling effective security education through hands-on log analysis and incident response practice.