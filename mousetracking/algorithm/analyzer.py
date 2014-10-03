'''
Created on Sep 11, 2014

@author: David Zwicker <dzwicker@seas.harvard.edu>

Contains a class that can be used to analyze results from the tracking
'''

from __future__ import division

import collections

import numpy as np
import networkx as nx

from .data_handler import DataHandler
from .objects import mouse

try:
    import pint
    UNITS_AVAILABLE = True
except (ImportError, ImportWarning):
    UNITS_AVAILABLE = False



class Analyzer(DataHandler):
    """ class contains methods to analyze the results of a video """
    
    use_units = True
    
    def __init__(self, *args, **kwargs):
        super(Analyzer, self).__init__(*args, **kwargs)
        
        if self.use_units and not UNITS_AVAILABLE:
            raise ValueError('Outputting results with units is not available. '
                             'Please install the `pint` python package.')

        # set the dimensions        
        self.time_scale = 1/self.data['video/fps']
        self.length_scale = self.data['pass2/pixel_size_cm']
        
        if self.use_units:
            # use a unit registry to keep track of all units
            self.units = pint.UnitRegistry()
            # define custom units
            self.units.define('frames = %g * second' % self.time_scale)
            self.units.define('pixel = %g * centimeter' % self.length_scale)
            # augment the dimension with the appropriate units
            self.time_scale *= self.units.second
            self.length_scale *= self.units.centimeter
        
    
    def get_burrow_lengths(self):
        """ returns a list of burrows containing their length over time """
        burrow_tracks = self.data['pass1/burrows/tracks']
        results = []
        for burrow_track in burrow_tracks:
            times = np.asarray(burrow_track.times)*self.time_scale
            lenghts = [burrow.length for burrow in burrow_track.burrows]
            data = np.c_[times, lenghts]
            results.append(data)
                  
        return results
    
    
    def get_mouse_state_transitions(self, states=None, len_threshold=0):
        """ returns the durations the mouse spends in each state before 
        transitioning to another state
        
        If states is given only, these states are included in the result.
        Transitions with a duration [in seconds] below len_threshold will
        not be included in the results.
        """
        try:
            mouse_state = self.data['pass2/mouse_trajectory'].states
        except KeyError:
            raise RuntimeError('The mouse trajectory has to be determined before '
                               'the transitions can be analyzed.')
            
        if states is None:
            states = mouse.STATES.keys()
            
        # get transitions
        transitions = collections.defaultdict(list)
        last_trans = 0
        for k in np.nonzero(np.diff(mouse_state) != 0)[0]:
            trans = (mouse_state[k], mouse_state[k + 1])
            duration = (k - last_trans)*self.time_scale
            if (trans[0] in states and trans[1] in states
                and duration > len_threshold):
                
                transitions[trans].append(duration)
            last_trans = k
            
        return transitions
            
    
    def get_mouse_transition_graph(self, **kwargs):
        """ calculate the graph representing the transitions between
        different states of the mouse """ 
        transitions = self.get_mouse_state_transitions(**kwargs)

        graph = nx.MultiDiGraph()
        nodes = collections.defaultdict(int)
        for trans, lengths in transitions.iteritems():
            # get node names 
            u = mouse.STATES[trans[0]]
            v = mouse.STATES[trans[1]]

            # get statistics            
            rate = 1/np.mean(lengths)
            nodes[u] += sum(lengths)

            # add the edge
            graph.add_edge(u, v, rate=rate, count=len(lengths))
        
        # add the nodes with additional data
        for node, duration in nodes.iteritems():
            graph.add_node(node, duration=duration)
        
        return graph
    
    
    def plot_mouse_transition_graph(self, ax=None, **kwargs):
        """ show the graph representing the transitions between
        different states of the mouse.
        
        Node size relates to the average duration the mouse spend there
        Line widths are related to the number of times the link was used
        Line colors relate to the transition rate between different states
        """
        import matplotlib.pyplot as plt
        from matplotlib.path import Path
        from matplotlib import patches, cm, colors, colorbar
        
        # get the transition graph
        graph = self.get_mouse_transition_graph(**kwargs)
        
        def log_scale(values, range_from, range_to):
            """ scale values logarithmically, where the interval range_from is
            mapped onto the interval range_to """
            values = np.asarray(values)
            log_from = np.log(range_from)
            scaled = (np.log(values) - log_from[0])/(log_from[1] - log_from[0])
            return scaled*(range_to[1] - range_to[0]) + range_to[0]
        
        # hard-coded node positions
        pos = {'unknown': (2, 2),
               'dimple': (0, 1),
               'air': (1.5, 3),
               'hill': (0, 2),
               'valley': (1.2, 1.5),
               'sand': (1.5, 0),
               'burrow': (0, 0)}

        # prepare the plot
        if ax is None:
            ax = plt.gca()
        ax.axis('off')

        # plot nodes
        nodes = graph.nodes(data=True)
        max_duration = max(node[1]['duration'] for node in nodes)
        node_sizes = log_scale([node[1]['duration'] for node in nodes],
                               range_from=(1, max_duration),
                               range_to=(10, 5000))
        nx.draw_networkx_nodes(graph, pos, node_size=node_sizes, ax=ax)
        
        # plot the edges manually because of directed graph
        edges = graph.edges(data=True)
        max_rate = max(edge[2]['rate'] for edge in edges)
        max_count = max(edge[2]['count'] for edge in edges)
        curve_bend = 0.08 #< determines the distance of the two edges between nodes
        colormap = cm.autumn
        for u, v, data in edges:
            # calculate edge properties
            width = log_scale(data['count'],
                              range_from=[10, max_count],
                              range_to=[1, 5])
            width = np.clip(width, 0, 10)
            color = colormap(data['rate']/max_rate)
            
            # get points
            p1, p2 = np.array(pos[u]), np.array(pos[v])
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            pm = np.array((p1[0] + dx/2 - curve_bend*dy,
                           p1[1] + dy/2 + curve_bend*dx))
        
            # plot Bezier curve
            codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3]
            path = Path((p1, pm, p2), codes)
            patch = patches.PathPatch(path, facecolor='none',
                                      edgecolor=color, lw=width)
            ax.add_patch(patch)
            
            # add arrow head
            if width > 1:
                pm = np.array((p1[0] + dx/2 - 0.75*curve_bend*dy,
                               p1[1] + dy/2 + 0.75*curve_bend*dx))
                dp = p2 - pm
                dp /= np.linalg.norm(dp)
                pc_diff = 0.1*dp
                pc2 = p2 - 0.6*dp
                ax.arrow(pc2[0], pc2[1], pc_diff[0], pc_diff[1],
                         head_width=0.1,
                         edgecolor='none', facecolor=color)
                
        # add a colorbar explaining the colorscheme
        cax = ax.figure.add_axes([0.87, 0.1, 0.03, 0.8])
        norm = colors.Normalize(vmin=0, vmax=1)
        cb = colorbar.ColorbarBase(cax, cmap=colormap, norm=norm,
                                   orientation='vertical', ticks=[0, 1])
        cb.set_label('Transition rate')
        cax.set_yticklabels(('lo', 'hi'))

        # plot the labels manually, since nx.draw_networkx_labels seems to be broken on mac
        for node in graph.nodes():
            x, y = pos[node]
            ax.text(x, y, node,
                    horizontalalignment='center',
                    verticalalignment='center')
        
        plt.sca(ax)
        return ax
                    
                
                    