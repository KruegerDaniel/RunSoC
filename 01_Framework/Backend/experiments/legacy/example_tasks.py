# Example tasks
tasks = {
    'RadarCapture': {
        'priority': 1,
        'period': 75,
        'execution_time': 2,
        'type': 'periodic',
        'deps': []
    },
    'CameraCapture': {
        'priority': 0,
        'period': 50,
        'execution_time': 7,
        'type': 'periodic',
        'deps': []
    },
    'SensorFusion': {
        'priority': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['RadarCapture', 'CameraCapture'],
    },
    'ObjectDetection': {
        'priority': 1,
        'execution_time': 15,
        'type': 'event',
        'deps': ['SensorFusion'],
    },
    'TrajectoryPrediction': {
        'priority': 1,
        'execution_time': 8,
        'type': 'event',
        'deps': ['ObjectDetection'],
    },
    'CollisionRiskAssessment': {
        'priority': 2,
        'execution_time': 3,
        'type': 'event',
        'deps': ['TrajectoryPrediction'],
    },
    'EmergencyBrakeDecision': {
        'priority': 2,
        'execution_time': 2,
        'type': 'event',
        'deps': ['CollisionRiskAssessment'],
    },
    'ActuatorControl': {
        'priority': 2,
        'execution_time': 1,
        'type': 'event',
        'deps': ['EmergencyBrakeDecision'],
    },
    'LaneMarkingDetection': {
        'priority': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['CameraCapture'],
    },
    'VehiclePositionEstimation': {
        'priority': 1,
        'execution_time': 4,
        'type': 'event',
        'deps': ['LaneMarkingDetection'],
    },
    'LaneDepartureWarning': {
        'priority': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringAngleCalculation': {
        'priority': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringActuatorControl': {
        'priority': 2,
        'execution_time': 1,
        'type': 'event',
        'deps': ['LaneDepartureWarning', 'SteeringAngleCalculation'],
    },

    # 'DistanceEstimation': {
    #     'priority': 1,
    #     'execution_time': 5,
    #     'type': 'event',
    #     'deps': ['ObjectDetection'],
    # },
    # 'RelativeSpeedEstimation': {
    #     'priority': 1,
    #     'execution_time': 4,
    #     'type': 'event',
    #     'deps': ['ObjectDetection'],
    # },
    # 'AdaptiveCruiseControlDecision': {
    #     'priority': 2,
    #     'execution_time': 6,
    #     'type': 'event',
    #     'deps': ['DistanceEstimation', 'RelativeSpeedEstimation'],
    # },
    # 'ThrottleControl': {
    #     'priority': 2,
    #     'execution_time': 2,
    #     'type': 'event',
    #     'deps': ['AdaptiveCruiseControlDecision'],
    # },
    # 'BrakeControl': {
    #     'priority': 2,
    #     'execution_time': 2,
    #     'type': 'event',
    #     'deps': ['AdaptiveCruiseControlDecision'],
    # },
}

tasks_long_path = {
    'Task1': {'priority': 1, 'execution_time': 15, 'type': 'periodic', 'period': 100, 'deps': []},
    'Task2': {'priority': 2, 'execution_time': 20, 'type': 'periodic', 'period': 180, 'deps': []},

    'Task3': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task1']},
    'Task4': {'priority': 4, 'execution_time': 30, 'type': 'event', 'deps': ['Task3']},
    'Task5': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task4']},
    'Task6': {'priority': 1, 'execution_time': 35, 'type': 'event', 'deps': ['Task5']},

    'Task7': {'priority': 2, 'execution_time': 40, 'type': 'event', 'deps': ['Task6']},
    'Task8': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task7']},
    'Task9': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task8']},
    'Task10': {'priority': 4, 'execution_time': 20, 'type': 'event', 'deps': ['Task9']},

    'Task11': {'priority': 2, 'execution_time': 45, 'type': 'event', 'deps': ['Task10']},
    'Task12': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task11']},
    'Task13': {'priority': 3, 'execution_time': 35, 'type': 'event', 'deps': ['Task12']},

    'Task14': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task13']},
    'Task15': {'priority': 3, 'execution_time': 40, 'type': 'event', 'deps': ['Task14']},
    'Task16': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task15']},

    'Task17': {'priority': 4, 'execution_time': 50, 'type': 'event', 'deps': ['Task16']},
    'Task18': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task17']},

    'Task19': {'priority': 4, 'execution_time': 35, 'type': 'event', 'deps': ['Task18']},
    'Task20': {'priority': 2, 'execution_time': 30, 'type': 'event', 'deps': ['Task19']},
}

tasks_balanced = {
    'Task1': {'priority': 1, 'execution_time': 15, 'type': 'periodic', 'period': 100, 'deps': []},
    'Task2': {'priority': 2, 'execution_time': 20, 'type': 'periodic', 'period': 180, 'deps': []},

    'Task3': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task1']},
    'Task4': {'priority': 4, 'execution_time': 30, 'type': 'event', 'deps': ['Task1']},
    'Task5': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task2']},
    'Task6': {'priority': 1, 'execution_time': 35, 'type': 'event', 'deps': ['Task2']},

    'Task7': {'priority': 2, 'execution_time': 40, 'type': 'event', 'deps': ['Task3', 'Task4']},
    'Task8': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task5', 'Task6']},
    'Task9': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task3']},
    'Task10': {'priority': 4, 'execution_time': 20, 'type': 'event', 'deps': ['Task4']},

    'Task11': {'priority': 2, 'execution_time': 45, 'type': 'event', 'deps': ['Task7']},
    'Task12': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task8']},
    'Task13': {'priority': 3, 'execution_time': 35, 'type': 'event', 'deps': ['Task9', 'Task10']},

    'Task14': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task11']},
    'Task15': {'priority': 3, 'execution_time': 40, 'type': 'event', 'deps': ['Task12']},
    'Task16': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task13']},

    'Task17': {'priority': 4, 'execution_time': 50, 'type': 'event', 'deps': ['Task14', 'Task15']},
    'Task18': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task16']},

    'Task19': {'priority': 4, 'execution_time': 35, 'type': 'event', 'deps': ['Task17', 'Task18']},
    'Task20': {'priority': 2, 'execution_time': 30, 'type': 'event', 'deps': ['Task19']},
}