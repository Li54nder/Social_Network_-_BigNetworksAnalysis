from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix as cm

import networkx as nx
import numpy as np
import sys


def detect_clusters_small(g):
    '''
    Metoda koja koristi klasu 'CompBFS' kako bi detektovala komponente povezanosti,
    vise o tome u opisu klase
    :param g: - pocetni graf kojem trebe detektovati klastere
    :return: - vraca skup skupova koji sadrze cvorove u istoj komponenti povezanosti
    '''
    c = CompBFS(g)
    return c.identify_components()


class CompBFS:
    '''
    Klasa koja sluzi za detektovanje povezanih komponenti i klastera
    unutar grafa, koristi BFS algoritam i primenjuje se samo za male mreze...
    '''

    visited = None
    components = None

    def __init__(self, g):
        self.G = g

    def identify_components(self):
        '''
        Metoda identifikuje povezane komponente unutar zadatog grafa koji je polje klase
        :return: - vraca skup skupova koji sadrze cvorove u istoj komponenti povezanosti
        '''
        self.visited = set()
        self.components = set()
        for n in self.G.nodes:
            if n not in self.visited:
                self.components.add(self.bfs(n))
        print(f"Graf ima {len(list(self.components))} klastera")
        return frozenset(self.components)

    def bfs(self, start):
        '''
        Metoda implementira BFS algoritam...
        :param start: cvor od koga krece pretraga
        :return: - vraca skup cvorova koji cine jednu komponentu povezanosti
        '''
        comp = set()
        queue = []
        comp.add(start)
        self.visited.add(start)
        queue.append(start)

        while len(queue) > 0:
            curr = queue.pop(0)
            neighbours = list(nx.neighbors(self.G, curr))
            for n in neighbours[:]:
                d1 = self.G.get_edge_data(curr, n)
                d2 = self.G.get_edge_data(n, curr)
                if d1['affinity'] is "-" or d2['affinity'] is "-":
                    neighbours.remove(n)
            for n in neighbours:
                if n not in self.visited:
                    comp.add(n)
                    self.visited.add(n)
                    queue.append(n)
        return frozenset(comp)


def detect_clusters_big_v4(g):
    '''
    Metoda koja detektuje klastere u velikim grafovima,
    ali metoda 'np.indices(mat.shape).T[:, :, [1, 0]]' ne moze da primi i obradi
    preveliku matricu (ali za ove potrebe radi sasvim prihvatljivo)...
    Ideja__ svim cvorovima dodati atribut rednog broja sto ce pomoci kod pravljenja matrice povezanosti,
    prolaskom kroz sve grane i uzimanjem 'endpoints' povezujemo ta dva cvora u matrici, a na pozicijama
    atributa cvorova (redni broj). Kasnije ce se preko labela spojiti cvorovi iz istih klastera (sa istim
    atriburima labela 'lbl')
    :param g: - graf za koji treba detektovati klastere
    :return: - vraca skup skupova koji sadrze cvorove u istoj komponenti povezanosti
    '''
    row = []
    col = []
    data = []

    g.nodes(data=True)
    nx.set_node_attributes(g, "", "serial_num")
    nx.set_node_attributes(g, "", "lbl")

    i = 0
    for n in g.nodes():
        g.add_node(n, serial_num=i)
        i += 1

    i = 1
    l = len(g.edges)
    for e in g.edges(data=True):
        sys.stdout.write(f"{i}/{l}")
        sys.stdout.flush()
        if e[2]['affinity'] is "+":
            row.append(dict(g.nodes(data=True)).get(e[0])['serial_num'])
            col.append(dict(g.nodes(data=True)).get(e[1])['serial_num'])
            data.append(1)
        i += 1
        sys.stdout.write("\r")

    n = len(g.nodes)
    mat = cm((np.asarray(data), (np.asarray(row), np.asarray(col))), shape=(n, n))

    n_comps, lbls = connected_components(mat, False)

    i = 0
    nodes = np.asarray(g.nodes(data=True))
    for lbl in lbls:
        nodes[i][1]['lbl'] = lbl
        i += 1

    clusters = set()
    for i in range(n_comps):
        cluster = [x for (x, d) in g.nodes(data=True) if d['lbl'] == i]
        clusters.add(frozenset(cluster))

    return clusters


def make_clusters2(clusters_set, g):
    '''
    Metoda od prosledjenog skupa skupova cvorova, koji predstavljaju klastere, pravi
    klastere kao grafove same za sebe, a na osnovu grafa 'g' koji je polazni graf
    //radi brzo i sa ovim kopiranjem...(mada bi mogao da se napravi graf samo
    //sa tim cvorovima i na osnovu povezanosti u pocetnom grafu ih povezati ili ne
    //ali je pitanje da li bi bilo brze jer treba da se proverava za svaka dva cvora da
    //da li su bila povezana...)
    :param clusters_set: - skup skupova cvorova
    :param g: - polazni graf
    :return: - skup klastera_grafova
    '''
    clusters = set()
    i = 1
    for c in clusters_set:
        tmp = set([x for x in c])  # int()
        new_g = g.copy()
        for n in list(new_g.nodes)[:]:
            if n not in tmp:
                new_g.remove_node(n)
        clusters.add(new_g)
        i += 1
    print("...napravljeni")
    return clusters


def detect_coalitions(clusters):
    '''
    Metoda detektuje koalicije i antikoalicije tako sto proveri svaki klaster da li sadrzi
    '-' granu koja bi od njega napravila antikoaliciju
    :param clusters: - skup klastera koji su mreza za sebe
    :return: - vraca listu koja na prvom mestu ima skup coalicija a na drugom skup antikoalicija
    '''

    double_set = []
    coalitions = set()
    anti_coalitions = set()
    for g in clusters:
        bad_edges = [(u, v) for (u, v, d) in g.edges(data=True) if d['affinity'] is "-"]
        if len(bad_edges) == 0:
            coalitions.add(g)
        else:
            anti_coalitions.add(g)
    double_set.append(coalitions)
    double_set.append(anti_coalitions)
    print("...detektovane")
    return double_set


def make_network_of_clusters(g, clusters):
    '''
    Pravljene mreze klastera...
    :param g: - pocetni graf na osnovu koga se proverava da li su klateri povezani medjusobno
    :param clusters: - skup klastera
    :return: - graf klastera
    '''
    new_g = nx.Graph()
    counter = 1
    for c in clusters:
        c.graph['name'] = str(counter)
        counter += 1
        new_g.add_node(c)
        
    for c1 in clusters:
        for c2 in clusters:
            if c1 == c2:
                continue
            connected = False
            counter = 0
            # Da li je neki cvor iz jednoh klastera sused nekom iz drugog...
            while not connected and counter < len(c1.nodes):
                n1 = list(c1.nodes)[counter]
                counter += 1
                for n2 in c2:
                    if n1 in nx.neighbors(g, n2):
                        connected = True
            if connected:
                new_g.add_edge(c1, c2)
    nx.set_edge_attributes(new_g, "-", "affinity")
    return new_g


def detect_bad_links(anticoalitions):
    '''
    Detektovanje grana koje narusavaju klasterabilnost
    :param anticoalitions: - svi klasteri antikoalicija koji sadrze '-' grane
    :return: - vraca se lista grana (parova cvorova) koje su '-' a unutar klastera su
    '''
    tmp_list = []
    for g in anticoalitions:
        bad_edges = [(u, v) for (u, v, d) in g.edges(data=True) if d['affinity'] is "-"]
        tmp_list.append(bad_edges)
    return [item for sub_list in tmp_list for item in sub_list]

