# Results Directory Documentation

## Overview

The results directory contains data analysis and visualization results from an actual HIKARI competition held on March 25, 2025. This provides real-world performance metrics, user behavior analysis, and platform effectiveness insights from live competition usage.

## Directory Structure

```
results/
└── EDA_competicao_25mar2025/    # Exploratory Data Analysis
    ├── process.py              # Data analysis script
    ├── logins.log              # Login attempt records
    ├── submissions.log         # Challenge submission records
    └── *.png                   # Visualization outputs
```

## Competition Data Analysis

### Data Sources

**Login Records** (`logins.log`):
- User authentication attempts
- Successful and failed logins
- IP address tracking
- Timestamp information
- Session management data

**Submission Records** (`submissions.log`):
- Challenge submission attempts
- Correct and incorrect answers
- Team performance metrics
- Timestamp correlation
- Flag verification results

### Analysis Script (`process.py`)

**Core Functionality**:
```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

def analyze_competition_data():
    """Main analysis function for competition data"""
    
    # Load data
    logins_df = pd.read_csv('logins.log', sep='\t')
    submissions_df = pd.read_csv('submissions.log', sep='\t')
    
    # Data preprocessing
    logins_df['timestamp'] = pd.to_datetime(logins_df['timestamp'])
    submissions_df['timestamp'] = pd.to_datetime(submissions_df['timestamp'])
    
    # Generate visualizations
    create_gantt_chart(submissions_df)
    create_submission_histogram(submissions_df)
    create_activity_heatmap(logins_df)
    create_kpm_distribution(logins_df)
    analyze_login_patterns(logins_df)
    
def create_gantt_chart(submissions_df):
    """Create Gantt chart showing user activity by challenge"""
    plt.figure(figsize=(12, 8))
    
    # Group by user and challenge
    user_activity = submissions_df.groupby(['user', 'challenge']).agg({
        'timestamp': ['min', 'max']
    }).reset_index()
    
    # Create Gantt bars
    for idx, row in user_activity.iterrows():
        start_time = row['timestamp']['min']
        end_time = row['timestamp']['max']
        plt.barh(row['user'], (end_time - start_time).seconds / 60, 
                left=(start_time - submissions_df['timestamp'].min()).seconds / 60,
                height=0.6, alpha=0.7)
    
    plt.xlabel('Time (minutes from start)')
    plt.ylabel('Users')
    plt.title('User Activity by Challenge - Gantt Chart')
    plt.tight_layout()
    plt.savefig('gantt_user_activity_by_challenge.png', dpi=300, bbox_inches='tight')
    plt.close()
```

## Visualization Outputs

### 1. Gantt Chart (`gantt_user_activity_by_challenge.png`)

**Purpose**: Shows when each user was active on different challenges
**Insights**:
- User engagement patterns throughout the competition
- Challenge difficulty correlation with time spent
- Team collaboration indicators
- Platform usage distribution

### 2. Submission Histogram (`histogram_corrects_wrongs_per_day.png`)

**Purpose**: Distribution of correct vs incorrect submissions
**Metrics**:
- Success rate per challenge
- Error patterns and common mistakes
- Learning curve analysis
- Platform difficulty assessment

### 3. KPM Distribution (`kpm_distribution.png`)

**Purpose**: Keystrokes per minute analysis
**Insights**:
- User typing speed correlation with performance
- Platform usability metrics
- Interface efficiency indicators
- User experience quality assessment

### 4. Activity Heatmap (`log_activity_heatmap.png`)

**Purpose**: Temporal activity patterns
**Analysis**:
- Peak usage hours
- User behavior patterns
- Platform load distribution
- Competition pacing insights

### 5. Login Analysis (`login_vs_invalid_attempts.png`)

**Purpose**: Security and authentication metrics
**Metrics**:
- Failed login attempts
- Authentication success rates
- Security incident indicators
- User access patterns

### 6. Submissions Timeline (`submissions_over_time.png`)

**Purpose**: Competition progression analysis
**Insights**:
- Challenge solving velocity
- Platform adoption rate
- User engagement retention
- Competition flow effectiveness

### 7. User Performance (`submissions_per_user.png`)

**Purpose**: Individual user performance metrics
**Analysis**:
- Submission frequency per user
- Performance distribution
- Outlier identification
- Engagement level assessment

### 8. Security Analysis (`top_invalid_ips.png`)

**Purpose**: Network security monitoring
**Insights**:
- Potential attack attempts
- Suspicious IP addresses
- Authentication security
- Platform protection effectiveness

## Key Findings

### Competition Performance

**Participation Metrics**:
- Total participants: [Analysis reveals actual numbers]
- Average session duration: [Calculated from login data]
- Challenge completion rate: [Derived from submissions]
- Platform uptime: [Monitored through logs]

**User Behavior Patterns**:
- Most active time periods during competition
- Challenge difficulty progression
- Team collaboration effectiveness
- Platform navigation efficiency

### Technical Insights

**System Performance**:
- Platform responsiveness under load
- Authentication system reliability
- Data processing efficiency
- Real-time log streaming performance

**Security Metrics**:
- Failed authentication attempts
- Suspicious access patterns
- Network security indicators
- Platform vulnerability assessment

### Educational Effectiveness

**Learning Outcomes**:
- Skill development progression
- Challenge difficulty calibration
- Knowledge retention indicators
- Training objective achievement

**Platform Usability**:
- Interface effectiveness
- User experience quality
- Navigation efficiency
- Feature utilization rates

## Usage Instructions

### Running the Analysis

1. **Data Preparation**:
   ```bash
   cd results/EDA_competicao_25mar2025/
   # Ensure logins.log and submissions.log are present
   ```

2. **Execute Analysis**:
   ```bash
   python process.py
   # Generates all visualization files
   ```

3. **View Results**:
   ```bash
   # Open generated PNG files
   ls -la *.png
   ```

### Data Format

**Login Log Format**:
```
timestamp	user_id	ip_address	status	session_id
2025-03-25T09:00:00Z	user1	192.168.1.45	success	sess_123
2025-03-25T09:01:15Z	user2	192.168.1.46	failed	sess_124
```

**Submission Log Format**:
```
timestamp	user_id	challenge_id	flag	status	team_id
2025-03-25T09:05:00Z	user1	chall_1	HIKARI{flag1}	correct	team_alpha
2025-03-25T09:06:30Z	user2	chall_1	HIKARI{wrong}	incorrect	team_beta
```

## Recommendations

### Platform Improvements

**Based on Analysis**:
1. **Performance Optimization**: Address peak load issues
2. **UI Enhancement**: Improve navigation based on user patterns
3. **Security Hardening**: Strengthen authentication mechanisms
4. **Feature Development**: Add requested functionality

### Competition Design

**Suggested Improvements**:
1. **Challenge Balancing**: Adjust difficulty based on completion rates
2. **Pacing Optimization**: Improve competition flow
3. **Team Features**: Enhance collaboration tools
4. **Real-time Feedback**: Provide better progress indicators

### Educational Impact

**Training Enhancements**:
1. **Skill Assessment**: Better measure learning outcomes
2. **Adaptive Difficulty**: Personalized challenge progression
3. **Knowledge Retention**: Improve long-term learning
4. **Practical Skills**: Focus on real-world applications

## Future Analysis

### Planned Enhancements

**Data Collection**:
- More granular user interaction tracking
- Performance metrics monitoring
- Security event correlation
- Learning outcome assessment

**Analysis Capabilities**:
- Machine learning for user behavior prediction
- Automated anomaly detection
- Real-time performance monitoring
- Predictive analytics for competition outcomes

This results directory provides valuable insights into the HIKARI platform's real-world performance and user behavior, enabling continuous improvement and validation of the educational and technical objectives.