"""
  Input / Output of Structures
  ============================

"""


import os
import re
from copy import deepcopy
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from pymol import cmd, importing


##  DOCKED STRUCTURES CLASS  ##########################################

class Docked():

    """
        Group of docked molecules class

        Attributes
        ----------
        entries : list
            'remarks' : dict
                str : float / int
            'internal' : dict
                'object' : str
                'state' : int
        pdb : list

        Properties
        ----------
        n_entries : int
        objects : set
        remarks : set
    """

    internal_empty = {'object':'', 'state': 0}

    def __init__(self):
        self.entries = []       # list of dict for every docked entry
        self.pdb = []

    @property
    def n_entries(self) -> int:
        return len(self.entries)

    @property
    def objects(self) -> set:
        return {i['internal']['object'] for i in self.entries}

    @property
    def remarks(self) -> set:
        if not self.entries:
            return set()
        else:
            # get all readed REMARKs
            return {j for i in self.entries for j in i['remarks'].keys()}

    def remove_ndx(self, ndx, update=True):
        """
            Remove a stored entry / pdb coordinates based on index

            Paramenters
            -----------
            ndx : int
                index of entry to remove
            update : bool
                update entries by decrement 'state' of same 'object' and 'ClusterRank' of same 'Cluster'
        """

        entry = self.entries[ndx]
        if update and 'Cluster' in self.remarks and 'ClusterRank' in self.remarks:
            for e in self.entries:
                if e['remarks']['Cluster'] == entry['remarks']['Cluster']:
                    e['remarks']['ClusterRank'] = e['remarks']['ClusterRank'] - int(e['remarks']['ClusterRank'] > entry['remarks']['ClusterRank'])
                if e['internal']['object'] == entry['internal']['object']:
                    e['internal']['state'] = e['internal']['state'] - int(e['internal']['state'] > entry['internal']['state'])
        del self.entries[ndx]
        del self.pdb[ndx]

    def load_dock4(self, cluster, object, mode):
        """
            Load a SwissDock's cluster of ligands from string list in PDB >Dock4 format

            Parameters
            ----------
            cluster : list of str
                list of string lines from cluster of structures in PDB format
            object : str
                name to be include the new object
            mode : {0, 1, 2}
                0 - all molecules to same object
                1 - only first molecule of each cluster to object (ClusterRank==0)
                2 - all molecules to multiple objects according to clusters
        """

        cluster = [line.strip() for line in cluster if line.strip()]

        self.__init__()

        # read all structures remarks/coordinates
        i = 0
        remark_re = re.compile(r'(?i)^REMARK\b\s+(\w+)\s*:\s*(-?\d+\.?\d*)')
        while i < len(cluster):

            pdb_keyword = cluster[i].split()[0].upper()

            # process docking information in REMARKs
            if pdb_keyword == 'REMARK':
                remarks = dict()
                # loop over REMARKs until no compliant found
                while remark_re.match(cluster[i]):
                    match = remark_re.match(cluster[i])
                    key = str(match.group(1))
                    value = float(match.group(2)) if key not in ('Cluster', 'ClusterRank') else int(match.group(2))
                    remarks[key] = value
                    i += 1

            # take whole molecule PDB coordinate lines
            elif pdb_keyword in ('ATOM', 'HETATM'):
                i_0 = i
                while cluster[i].split()[0].upper() in ('ATOM', 'HETATM'):
                    i += 1
                pdb_molecule = "\n".join(cluster[i_0:i]) + '\nENDMDL\n'

                # append to main attribute at the end of molecule
                self.pdb.append(pdb_molecule)
                self.entries.append({'remarks':remarks, 'internal':deepcopy(self.internal_empty)})

            else:
                i += 1

        # equalize remarks for all entries
        for n, i in enumerate(self.entries):
            for j in self.remarks:
                i['remarks'].setdefault(j, None)
            # set internals
            i['internal']['object'] = object
            i['internal']['state'] = n + 1

        # check if defined Cluster and ClusterRank
        if mode in ('1', '2') and not 'Cluster' in self.remarks or not 'ClusterRank' in self.remarks:
            print(" PyViewDock: Failed splitting while loading. Missing 'Cluster' or 'ClusterRank'.")
            return

        # load only first of every cluster (ClusterRank == 0)
        if mode == '1':
            entries, pdb = [], []
            n_state = 0
            for e,p in zip(self.entries, self.pdb):
                if e['remarks']['ClusterRank'] == 0:
                    pdb.append(p)
                    entries.append(e)
                    n_state += 1
                    entries[-1]['internal']['state'] = n_state

            self.entries, self.pdb = deepcopy(entries), deepcopy(pdb)
            cmd.read_pdbstr("".join(self.pdb), object)

        # load all in different objects by Cluster
        elif mode == '2':
            pdb = dict()
            for e,p in zip(self.entries, self.pdb):
                object_new = object + '-' + str(e['remarks']['Cluster'])
                pdb.setdefault(object_new, []).append(p)
                e['internal']['object'] = object_new
                e['internal']['state'] = len(pdb[object_new]) + 1
            for object_new, p in pdb.items():
                cmd.read_pdbstr("".join(p), object_new)

        # load all in one object
        else:
            cmd.read_pdbstr("".join(self.pdb), object)

    def sort(self, remark, reverse=False):
        """
            Sort entries according to values of 'remark'

            Parameters
            ----------
            remark : str
                field to use as sorting guide
            reverse : bool
                direction of sorting (False/True : Ascending/Descending)
        """

        if remark not in self.remarks:
            raise ValueError("Unkown 'remark' to sort by")

        self.entries = sorted(self.entries, key=lambda k: k['remarks'][remark], reverse=reverse)


##  GLOBAL VARIABLES  #################################################

docked = Docked()


##  FUNCTIONS  ########################################################

def load_dock4(filename, object='', mode=0):
    """
        Load a SwissDock's cluster of ligands as an object
        with multiple states and read the docking information

        Parameters
        ----------
        filename : str
            cluster of structures in PDB format
        object : str
            name to be include the new object
            if absent, taken from filename
        mode : {0, 1, 2}
            0 - all molecules to same object
            1 - only first molecule of each cluster to object
            2 - all molecules to multiple objects according to clusters
    """

    global docked

    if not object:
        object = os.path.basename(filename).split('.')[0]

    # read file as list of strings
    with open(filename, "rt") as f:
        cluster = f.readlines()

    docked.load_dock4(cluster, object, mode)
    print(f" PyViewDock: \"{filename}\" loaded as \"{object}\"")


def load_chimerax(filename):
    """
        Load a UCSF ChimeraX file written by SwissDock

        Parameters
        ----------
        filename : str
            chimerax file (XML file with URL of target and ligands cluster)
    """

    # UCSF Chimera Web Data Format
    # www.cgl.ucsf.edu/chimera/docs/ContributedSoftware/webdata/chimerax.html

    global docked

    print(f" PyViewDock: Loading \"{filename}\"")

    with open(filename, "rt") as f:
        chimerax_file = f.read()

    pdb_url = re.findall('"(http:[^"]+pdb)"', chimerax_file)

    if len(pdb_url) == 2:
        target_url, cluster_url = pdb_url
        try:
            target_pdb = urlopen(target_url).read().decode('utf-8')
            cluster_pdb = urlopen(cluster_url).readlines()
            cluster_pdb = [i.decode('utf-8') for i in cluster_pdb]
        except HTTPError:
            print(" PyViewDock: Failed reading 'chimerax' file. Bad server response. File too old?")
        else:
            cmd.read_pdbstr(target_pdb, 'target')
            docked.load_dock4(cluster_pdb, 'cluster', 0)
    else:
        print(" PyViewDock: Failed reading 'chimerax' file. Inconsistent format.")


def load_ext(filename, object='', state=0, format='', finish=1,
             discrete=-1, quiet=1, multiplex=None, zoom=-1, partial=0,
             mimic=1, object_props=None, atom_props=None, *, _self=cmd):
    """
        Wrapper to load function with extended funtionality

        Formats
        -------
        .chimerax
            XML file with URL of target and ligands cluster
    """

    if not format:
        file_dot_separated = os.path.basename(filename).rpartition('.')
        name   = "".join(file_dot_separated[:-2])
        format = file_dot_separated[-1]

    # Chimera X
    if format.lower() == "chimerax":
        load_chimerax(filename)

    # original load function
    else:
        importing.load(filename, object, state, format, finish,
                        discrete, quiet, multiplex, zoom, partial)
