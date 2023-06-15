import streamlit as st
from streamlit_agraph import agraph, TripleStore, Node, Edge, Config
import pandas as pd
from rdflib import Graph, URIRef, Namespace, Literal
from rdflib.namespace import RDF, RDFS, SKOS
from rdflib.plugins.sparql import prepareQuery
import re
from pathlib import Path
import os
from urllib.parse import urlparse
import requests

def is_valid_url(url):
    result = urlparse(url)
    return all([result.scheme, result.netloc])

@st.cache_data
def load_ontology():
    emmo                        = 'https://emmo-repo.github.io/versions/1.0.0-beta3/emmo-inferred.ttl'
    quantities                  = 'https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/isq_bigmap.ttl'
    units                       = 'https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/unitsextension_bigmap.ttl'
    electrochemical_quantities  = 'https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/electrochemicalquantities.ttl'
    electrochemistry            = 'https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/electrochemistry.ttl'
    battery_quantities          = 'https://raw.githubusercontent.com/emmo-repo/domain-battery/master/batteryquantities.ttl'
    battery                     = 'https://raw.githubusercontent.com/emmo-repo/domain-battery/master/battery.ttl'
    materials                   = 'https://raw.githubusercontent.com/emmo-repo/domain-electrochemistry/master/material_bigmap_temp.ttl'

    g= Graph()
    g.parse(emmo, format='ttl')
    g.parse(quantities, format='ttl')
    g.parse(units, format='ttl')
    g.parse(electrochemical_quantities, format='ttl')
    g.parse(electrochemistry, format='ttl')
    g.parse(battery_quantities, format='ttl')
    g.parse(battery, format='ttl')
    g.parse(materials, format='ttl')
    
    # Create a dictionary to hold the mappings
    label_uri_dict = {}
    uri_label_dict = {}

    # Iterate through all the triples in the graph
    for subj, pred, obj in g:
        # Check if the predicate is `skos:prefLabel`
        if pred == SKOS.prefLabel and isinstance(obj, Literal):
            # Store the URI and prefLabel in the dictionary
            label_uri_dict[obj.value] = subj
            uri_label_dict[str(subj)] = obj.value
            
    return g, label_uri_dict, uri_label_dict

@st.cache_data
def load_knowledge_graph():
    # set directory information
    thisdir = Path(__file__).resolve().parent
    peopledir = thisdir / 'people'
    
    # Define the schema.org namespace
    schema = Namespace("http://schema.org/")

    # schema          = 'https://schema.org/version/latest/schemaorg-current-https.ttl'
    # persons         = 'https://raw.githubusercontent.com/BIG-MAP/BatteryKnowledgeGraph/main/persons.json'
    # organizations   = 'https://raw.githubusercontent.com/BIG-MAP/BatteryKnowledgeGraph/main/organizations.json'
    # projects        = 'https://raw.githubusercontent.com/BIG-MAP/BatteryKnowledgeGraph/main/projects.json'

    g= Graph()
    # #g.parse(schema, format='ttl')
    # g.parse(persons, format='json-ld')
    # g.parse(organizations, format='json-ld')
    # g.parse(projects, format='json-ld')

    # Get metadata examples
    # loop through all the files in the directory
    for filename in os.listdir(peopledir):
        # check if the file is a JSON-LD file
        if filename.endswith(".json"):
            # open the file and read its contents into a string
            with open(os.path.join(peopledir, filename), "r") as f:
                jsonld_string = f.read()
            # parse the JSON-LD string and add the resulting triples to the graph
            g.parse(data=jsonld_string, format="json-ld")         
            
    
    query_text = """
    PREFIX schema: <http://schema.org/>

    SELECT ?s ?p ?o
    WHERE {
    ?s a schema:Person ;
        schema:affiliation ?o .
    ?s ?p ?o .
    }
    """
    results = g.query(query_text)
    for row in results:
        org = str(row.o)
        rorid = org.split("/")[-1]
        rorapi = "https://api.ror.org/organizations/"
        url = rorapi + rorid
        response = requests.get(url)
        if response.status_code == 200:
            orgdata = response.json()
        # Define the latitude and longitude values
        latitude = Literal(orgdata["addresses"][0]["lat"])  # Example latitude value
        longitude = Literal(orgdata["addresses"][0]["lng"]) # Example longitude value
        
        # Add triples for latitude and longitude using the geo property
        g.add((row.o, RDF.type, schema.Organization))
        g.add((row.o, schema.latitude, latitude))
        g.add((row.o, schema.longitude, longitude))
        g.add((row.o, schema.name, Literal(orgdata["name"])))
            
    # Create a dictionary to hold the mappings
    label_uri_dict = {}
    uri_label_dict = {}

    # Iterate through all the triples in the graph
    for subj, pred, obj in g:
        # Check if the predicate is `skos:prefLabel`
        if pred == schema.name:
            # Store the URI and prefLabel in the dictionary
            label_uri_dict[obj.value] = subj
            uri_label_dict[str(subj)] = obj.value
            
    return g, label_uri_dict, uri_label_dict

def get_datasets(G, g):
    # project_list = options["project"]
    # for project_id in project_list:
    projects = {
        "Battery2030+": "https://doi.org/10.3030/957213", 
        "BIG-MAP": "https://doi.org/10.3030/957189", 
        "BAT4EVER": "https://doi.org/10.3030/957225",
        "HIDDEN": "https://doi.org/10.3030/957202", 
        "INSTABAT": "https://doi.org/10.3030/955930", 
        "SPARTACUS": "https://doi.org/10.3030/957202", 
        "SENSIBAT": "https://doi.org/10.3030/957273"}

    selected_project_keys = st.multiselect("Project", list(projects.keys()))
    project_id_list = [projects[option] for option in selected_project_keys]

    query_template = '''
    PREFIX schema: <https://schema.org/>
    PREFIX qb: <http://purl.org/linked-data/cube#>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX echem: <mhttp://emmo.info/electrochemistry#>
    PREFIX batt: <http://emmo.info/battery#>

    SELECT ?s ?p ?o
    WHERE {{
    ?s a qb:DataSet ;
        schema:isPartOf ?project ;
        dcterms:subject ?cell .
    ?project a schema:ResearchProject .
    {filter}
    ?s ?p ?o .
    }}
    '''

    filter_statement = ""

    # if len(project_id_list) !=0:
    filter_template = 'FILTER({filter_value}) .'
    project_filter_template = '?project={project_id}'

    # Define a list of filters
    #project_id_list = ["<https://doi.org/10.3030/957202>", "<https://doi.org/10.3030/957189>"]

    # Create a list of filter strings using the filter template
    filter_strings = [project_filter_template.format(project_id=f) for f in project_id_list]
    #st.write(filter_strings)

    # Join the filter strings with " || " to create a single filter string with OR logic
    joined_filter = ' || '.join(filter_strings)
    filter_statement = filter_template.format(filter_value=joined_filter)

    # st.write(filter_statement)

    #filter_statement = ""
    # Format the query string with the filter string
    query_text = query_template.format(filter=filter_statement)
    #st.write(query_text)

    # query_text = f"""
    # PREFIX schema: <https://schema.org/>
    # PREFIX qb: <http://purl.org/linked-data/cube#>

    # SELECT ?s ?p ?o
    # WHERE {{
    # ?s a qb:DataSet ;
    #     schema:isPartOf ?project .
    # ?project a schema:ResearchProject .
    # FILTER(?project=<https://doi.org/10.3030/957202> || ?project=<https://doi.org/10.3030/957189>) .
    # ?s ?p ?o .
    # }}
    # """
    results = G.query(query_text)
    for row in results:
        g.add((row.s, row.p, row.o))
    return g

def get_time_column(g, iri):
    order = []
    query_text = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <https://schema.org/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX qb: <http://purl.org/linked-data/cube#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX echem: <http://emmo.info/electrochemistry#>
    SELECT ?order
    WHERE {{
    <{iri}> dcat:structure ?struct .
    ?struct dcat:component ?comp .
    ?comp qb:dimension echem:electrochemistry_27b3799c_250c_4332_8b71_7992c4a7bb05 .
    ?comp qb:order ?order
    }}
    """
    #?ds dcterms:subject <{iri}> .
    results = g.query(query_text)
    for row in results:
        order.append(row.order.value)

    return order[0]

def get_voltage_column(g, iri):
    order = []
    query_text = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <https://schema.org/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX qb: <http://purl.org/linked-data/cube#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX echem: <http://emmo.info/electrochemistry#>
    SELECT ?order
    WHERE {{
    <{iri}> dcat:structure ?struct .
    ?struct dcat:component ?comp .
    ?comp qb:dimension <http://emmo.info/electrochemistry#electrochemistry_4ebe2ef1_eea8_4b10_822d_7a68215bd24d> .
    ?comp qb:order ?order
    }}
    """
    #?ds dcterms:subject <{iri}> .
    results = g.query(query_text)
    for row in results:
        order.append(row.order.value)

    return order[0]

def get_current_column(g, iri):
    order = []
    query_text = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <https://schema.org/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    PREFIX qb: <http://purl.org/linked-data/cube#>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    PREFIX echem: <http://emmo.info/electrochemistry#>
    SELECT ?order
    WHERE {{
    <{iri}> dcat:structure ?struct .
    ?struct dcat:component ?comp .
    ?comp qb:dimension <http://emmo.info/electrochemistry#electrochemistry_637ee9c4_4b3f_4d3a_975b_c0572dfe53ce> .
    ?comp qb:order ?order
    }}
    """
    #?ds dcterms:subject <{iri}> .
    results = g.query(query_text)
    for row in results:
        order.append(row.order.value)

    return order[0]

def filter_projects(dg, dg_p, id):
    # project_list = options["project"]
    # for project_id in project_list:

    query_text = f"""
    PREFIX schema: <https://schema.org/>
    PREFIX qb: <http://purl.org/linked-data/cube#>

    SELECT ?s ?p ?o
    WHERE {{
    ?s schema:isPartOf <{id}> .
    ?s ?p ?o .
    }}
    """
    results = dg.query(query_text)
    for row in results:
        dg_p.add((row.s, row.p, row.o))
    return dg_p

def get_cells(G, g):
    query_text = """
    PREFIX schema: <https://schema.org/>
    PREFIX qb: <http://purl.org/linked-data/cube#>
    PREFIX batt: <http://emmo.info/battery#>

    SELECT ?s ?p ?o
    WHERE {
    ?s a batt:battery_392b3f47_d62a_4bd4_a819_b58b09b8843a .
    ?s ?p ?o .
    }
    """
    results = G.query(query_text)
    for row in results:
        g.add((row.s, row.p, row.o))
    return g

def get_node(G, g, node):
    query_text = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <https://schema.org/>

    SELECT ?s ?p ?o
    WHERE {{
    <{node}> ?p ?o .
    FILTER(isIRI(?o))
    }}
    """
    results = G.query(query_text)
    for row in results:
        g.add((node, row.p, row.o))
    return g

def get_type(G, g, type):
    for item in type:
        query_text = f"""
        PREFIX schema: <https://schema.org/>

        SELECT ?s ?p ?o
        WHERE {{
        {{
        ?s a <{item}> ;
            schema:isPartOf ?o .
        }}
        UNION
        {{
        ?s a <{item}> ;
            schema:affiliation ?o .
        }}
        ?s ?p ?o .
        }}
        """
        results = G.query(query_text)
        for row in results:
            g.add((row.s, row.p, row.o))
    return g

def get_projects(G, g):
    query_text = """
    PREFIX schema: <https://schema.org/>

    SELECT ?s ?p ?o
    WHERE {
    ?s a schema:ResearchProject ;
        schema:isPartOf ?o .
    ?s ?p ?o .
    }
    """
    results = G.query(query_text)
    for row in results:
        g.add((row.s, row.p, row.o))
    return g

def get_organizations(G, g):
    query_text = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX schema: <https://schema.org/>

    SELECT ?s ?p ?o
    WHERE {
    {
    ?s rdf:type schema:Organization ;
        schema:isPartOf ?o .
    }
    UNION
    {
    ?s rdf:type schema:ResearchOrganization ;
        schema:isPartOf ?o .
    }
    UNION
    {
    ?s rdf:type schema:CollegeOrUniversity ;
        schema:isPartOf ?o .
    }
    ?s ?p ?o .
    }
    """
    results = G.query(query_text)
    for row in results:
        g.add((row.s, row.p, row.o))
    return g

def get_persons(G, g):
    query_text = """
    PREFIX schema: <http://schema.org/>

    SELECT ?s ?p ?o
    WHERE {
    ?s a schema:Person ;
        schema:affiliation ?o .
    ?s ?p ?o .
    }
    """
    results = G.query(query_text)
    for row in results:
        g.add((row.s, row.p, row.o))
        #st.write(row)
    return g

def visualize_graph(G, g, uri_label_dict):
    # Define the graph visualization
    nodes = []
    edges = []
    seen_nodes = set()

    for s, p, o in g:
        source = str(s)
        target = str(o)
        predicate = str(p)
        image_url = ""
        
        #st.write()

        if is_valid_url(target) and target not in seen_nodes:
            
            if re.search(r'#(\w+)', target):
                node_label = re.search(r'#(\w+)', target).group(1)
            elif target in uri_label_dict.keys():
                node_label = uri_label_dict[target]
            else:
                node_label = ""

            nodes.append(Node(id = target, label = node_label))
            seen_nodes.add(target)

        if source not in seen_nodes:
            if source in uri_label_dict:
                node_label = uri_label_dict[source]
            else:
                node_label = ""
            
            results = G.query(f"""
                PREFIX schema: <http://schema.org/>
                SELECT ?image
                WHERE {{
                <{s}> schema:image ?image .
                }}
                """)
            for row in results:
                image_url = str(row.image)

            if image_url[:4] == "http":
                #image_url = 'https://raw.githubusercontent.com/BIG-MAP/FAIRBatteryData/json-ld/app/images/simon.clark-sintef.no.jpg'
                nodes.append(Node(id = source, label = node_label, shape="circularImage", image = image_url))
                image_url = ""
            else:
                nodes.append(Node(id = source, label = node_label))
            seen_nodes.add(source)
        
        if predicate in uri_label_dict:
            edge_label = ""#uri_label_dict[predicate]
        elif re.search(r'#(\w+)', predicate):
            edge_label = ""#re.search(r'#(\w+)', predicate).group(1)
        elif predicate == 'http://purl.org/dc/terms/creator':
            edge_label = 'creator'
        else:
            edge_label = ''
        edges.append( Edge( source=source, target = target, label = edge_label))

    # config = Config(width=1500,
    #                 height=950,
    #                 center=True,
    #                 directed=True, 
    #                 physics=False, 
    #                 solver = 'barnesHut',
    #                 stabilize = True,
    #                 fit = True,
    #                 hierarchical=False,
    #                 levelSeparation = 150,
    #                 nodeSpacing = 100,
    #                 treeSpacing = 200,
    #                 blockShifting = True,
    #                 edgeMinimization = True,
    #                 parentCentralization = True,
    #                 direction = 'UD',
    #                 sortMethod = 'hubsize',
    #                 shakeTowards = 'roots',
    #                 # **kwargs
    #                 )
    
    config = Config(width=750,
                height=950,
                directed=True, 
                physics=True, 
                hierarchical=False,
                levelSeparation = 300,
                nodeSpacing = 100,
                treeSpacing = 400,
                # **kwargs
                )

    ag = agraph(nodes=nodes, edges=edges, config=config)