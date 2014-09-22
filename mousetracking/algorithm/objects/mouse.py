'''
Created on Sep 11, 2014

@author: David Zwicker <dzwicker@seas.harvard.edu>
'''

from __future__ import division

import numpy as np

from utils import LazyHDFValue



STATE_ENCODING_DOCUMENTATION = """
The location is encoded in the last two digits
0      = mouse location is unknown

10..19 = mouse is overground
    11 = mouse is in the air
    12 = mouse is on either hill
    13 = mouse is in the valley

20..29 = mouse is underground
    21 = mouse is in any burrow
"""

VALID_STATES = (0, 10, 11, 12, 13, 20, 21)



def state_to_int(state):
    """ calculate the integer representing the mouse state """
    value = 0
    
    # investigate the mouse position
    # Note that underground can also be None and we thus have to
    # explicitly compare with True/False
    underground = state.pop('underground', None)
    if underground == False:
        value += 10
        location = state.pop('location')
        if  location == 'air':
            value += 1
        elif location == 'hill':
            value += 2
        elif location == 'valley':
            value += 3
        else:
            state['location'] = location
            
    elif underground == True:
        value += 20
        if state.get('location') == 'burrow':
            value += 1
            state.pop('location')

    if state:
        raise RuntimeError('Some state information cannot be interpreted: %s' % state)

    return value



def int_to_state(value):
    """ reconstruct the state dictionary from an integer """
    state = {}
    
    value_loc = (value % 10)
    if 10 <= value_loc < 20:
        state['underground'] = False
        if value_loc == 11:
            state['location'] = 'air'
        elif value_loc == 12:
            state['location'] = 'hill'
        elif value_loc == 13:
            state['location'] = 'valley'
            
    elif 20 <= value_loc < 30:
        state['underground'] = True
        if value_loc == 21:
            state['location'] = 'burrow'
    
    return state


def query_state(states, query):
    """ returns a boolean value/array where query is True """
    if query == 'underground':
        return (10 <= states) & (states < 20)
    elif query == 'in_air':
        return states == 11
    elif query == 'on_hill':
        return states == 12
    elif query == 'in_valley':
        return states == 13
    elif query == 'underground':
        return (20 <= states) & (states < 30)
    elif query == 'in_burrow':
        return states == 21
    else:
        raise ValueError('Unknown query `%s`' % query)



class MouseTrack(object):
    """ class that describes the mouse track """
    
    hdf_attributes = {'column_names': ('Position X', 'Position Y', 'Status')}
    storage_class = LazyHDFValue
    
    def __init__(self, trajectory, states=None):
        self.pos = trajectory
        if states is not None:
            self.states = states
        else:
            self.states = np.zeros(len(trajectory), np.int)
    
        
    def __repr__(self):
        return '%s(frames=%d)' % (self.__class__.__name__, len(self.pos))
    
    
    def set_state(self, frame_id, state):
        self.states[frame_id] = state_to_int(state)
    
    
    def query_state(self, query):
        return query_state(self.states, query)
    
    
    def to_array(self):
        return np.c_[self.pos, self.states]
    
    
    @classmethod
    def create_from_array(cls, data):
        return cls(data[:, :2], data[:, 2])



def test_state_conversion():
    """ simple test function for the state conversion """
    for value in xrange(0, 100):
        state = int_to_state(value)
        if state and value != state_to_int(state):
            raise AssertionError('Failed: %d != %s' % (value, state))
    print('The test was successful.') 



if __name__ == '__main__':
    print('Test the state to value conversion')
    test_state_conversion()