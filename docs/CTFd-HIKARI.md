# CTFd-HIKARI Documentation

## Overview

CTFd-HIKARI is a heavily modified fork of the CTFd platform, transformed into a Blue Team competition platform focused on log analysis and incident response. The modifications were primarily made by 0xLeonardoChahud to create a unique competition environment where teams analyze security logs to find indicators of compromise.

## Key Modifications

### 1. HIKARI Plugin System (`CTFd/plugins/hikari-plugin/`)

The core enhancement that transforms CTFd into a Blue Team platform.

#### Plugin Structure
```
hikari-plugin/
├── __init__.py          # Main plugin logic and routes
├── config.json          # Plugin metadata
├── hikari_forms/        # Form definitions for UI
├── hikari_importer/     # Import/export functionality
├── hikari_kibana/       # Elasticsearch/Kibana integration
├── hikari_models/       # Database models
└── templates/           # Admin interface templates
```

#### Core Features

**Competition Management**
- Start/stop/reset competition functionality
- Automatic log injection based on challenge progression
- Team isolation with individual Kibana spaces

**Database Models** (`hikari_models/__init__.py`):
- `Zerotier`: Stores network configurations for team isolation
- `ZerotierConfig`: Maps teams to Zerotier networks

**Routes and Endpoints**:
- `/admin/plugins/hikari`: Main admin interface
- `/admin/plugins/hikari/import`: Competition import
- `/admin/plugins/hikari/notify`: Bulk notification system
- `/admin/plugins/hikari/zerotier`: Network management

### 2. HIKARI Challenge Type (`CTFd/plugins/hikari_challenge/`)

A custom challenge type specifically designed for log analysis competitions.

#### Features
- **JSON Log Storage**: Challenges store security logs as JSON data
- **Kafka Integration**: Logs are streamed to Elasticsearch via Kafka
- **Prerequisite System**: Challenges can depend on others being solved first
- **Progressive Activation**: Logs are injected only when prerequisites are met

#### Implementation Details
```python
# Challenge model extension
class HikariChallengeModel(ChallengeModel):
    chall_logs = db.Column(JSON)  # Stores the log data
    logs_activated = db.Column(Boolean, default=False)
    is_first_challenge = db.Column(Boolean, default=False)
```

#### Kafka Configuration
- **Topic**: `competition1`
- **Development**: Simple bootstrap configuration
- **Production**: SASL_SSL with SCRAM-SHA-512 authentication

### 3. HIKARI Theme (`CTFd/themes/hikari-theme/`)

A complete visual redesign with modern UI elements.

#### Key Changes
- **Framework**: Materialize CSS for Material Design
- **Responsive Design**: Mobile-optimized layouts
- **Dark Mode**: Toggle between light and dark themes
- **Custom Branding**: HIKARI-specific imagery and styling

#### Structure
```
hikari-theme/
├── assets/              # Source files (JS, CSS)
├── static/              # Compiled assets
├── templates/           # HTML templates
├── package.json         # Dependencies
└── vite.config.js       # Build configuration
```

### 4. Elasticsearch/Kibana Integration

Deep integration for log analysis capabilities.

#### Kibana Management (`hikari_kibana/__init__.py`)

**User Creation**:
```python
def create_kibana_user(username, password):
    # Creates Elasticsearch user with specific index permissions
    # Assigns read-only role for team's data
```

**Space Management**:
```python
def create_kibana_space(team_name):
    # Creates isolated Kibana space
    # Sets up index patterns
    # Configures dashboards
```

#### Configuration
- **Elasticsearch URL**: Configured via environment or default to `http://elastic:9200`
- **Kibana URL**: Configured via environment or default to `http://kibana:5601`
- **Index Pattern**: `logs-*` for all team data

### 5. Email/SMTP Enhancements

Advanced notification system for competition management.

#### Features
- **Bulk Notifications**: Send updates to all teams or specific groups
- **Automatic Credentials**: Teams receive Kibana login info via email
- **Network Details**: Zerotier configuration sent automatically

#### Email Templates
- Team assignment notifications
- Kibana credentials delivery
- Competition updates
- Network configuration details

### 6. Log Injection System

The core mechanism for progressive challenge delivery.

#### Workflow
1. **Challenge Upload**: Admin uploads challenge with JSON logs
2. **Initial Injection**: First challenges' logs injected at competition start
3. **Progressive Activation**: As teams solve challenges, dependent logs activate
4. **Kafka Streaming**: Logs sent to Kafka topic for Logstash processing
5. **Elasticsearch Storage**: Logs indexed with team-specific metadata

#### Kafka Producer Configuration
```python
# Production configuration with authentication
producer_config = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'security.protocol': 'SASL_SSL',
    'sasl.mechanism': 'SCRAM-SHA-512',
    'sasl.username': KAFKA_USERNAME,
    'sasl.password': KAFKA_PASSWORD
}
```

### 7. Competition Management Interface

Enhanced admin interface for competition control.

#### Features
- **Status Dashboard**: Real-time view of competition state
- **Bulk Operations**: Team management, notification sending
- **Log Monitoring**: Track which logs have been activated
- **Reset Capability**: Clean competition reset functionality

### 8. Import/Export System

Custom backup and restore functionality.

#### Capabilities
- Complete competition state preservation
- Challenge configurations with logs
- Team and user data
- Zerotier network mappings
- File uploads and assets

## Configuration

### Environment Variables
```bash
# Elasticsearch/Kibana
ELASTIC_URL=http://elasticsearch:9200
KIBANA_URL=http://kibana:5601

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_USERNAME=user1
KAFKA_PASSWORD=password

# Zerotier (optional)
ZEROTIER_CONTROLLER_URL=http://zerotier:9993
```

### Docker Deployment
```yaml
# docker-compose.yml additions
environment:
  - ELASTIC_URL=http://elasticsearch:9200
  - KIBANA_URL=http://kibana:5601
  - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

## Usage

### Competition Setup
1. **Configure Infrastructure**: Deploy ELK stack and Kafka
2. **Create Teams**: Standard CTFd team creation
3. **Upload Challenges**: Use HIKARI challenge type with JSON logs
4. **Set Prerequisites**: Define challenge dependencies
5. **Configure Networks**: Optional Zerotier setup
6. **Start Competition**: Click "Start Competition" in admin panel

### During Competition
- Teams receive Kibana credentials via email
- Initial challenge logs are automatically injected
- Solving challenges triggers dependent log activation
- Teams analyze logs in isolated Kibana spaces
- Progress tracked through standard CTFd scoring

### Competition Management
- Monitor log activation status
- Send bulk notifications
- Reset competition if needed
- Export/import competition state

## Technical Architecture

### Data Flow
```
Challenge JSON → Kafka Producer → Kafka Topic → Logstash → Elasticsearch → Kibana
                                                                              ↑
                                                                         Team Access
```

### Database Schema Extensions
- `challenges.chall_logs`: JSON field for log data
- `challenges.logs_activated`: Boolean tracking injection status
- `challenges.is_first_challenge`: Boolean for initial challenges
- `zerotier.*`: Tables for network configuration

### API Endpoints
- `/api/v1/challenges` (extended): Includes HIKARI-specific fields
- `/admin/plugins/hikari/*`: Plugin administration routes

## Development

### Local Setup
1. Standard CTFd development setup
2. Additional services: Elasticsearch, Kibana, Kafka
3. Configure environment variables
4. Run with docker-compose

### Testing
- Plugin tests in `CTFd/plugins/hikari-plugin/tests/`
- Challenge type tests in `CTFd/plugins/hikari_challenge/tests/`
- Integration tests require full ELK stack

## Migration from Standard CTFd

1. **Database Migration**: Run standard Alembic migrations
2. **Plugin Installation**: Plugins auto-load from directory
3. **Theme Selection**: Set hikari-theme in admin config
4. **Service Configuration**: Add ELK and Kafka connections
5. **Team Migration**: Existing teams work without modification