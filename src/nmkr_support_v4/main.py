#!/usr/bin/env python
import sys
import warnings

import nmkr_support_v4.crew as crew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Run the crew.
    """
    inputs = {
        'support_request': 'How much does it cost to use NMKR?'
    }
    crew().kickoff(inputs=inputs)
