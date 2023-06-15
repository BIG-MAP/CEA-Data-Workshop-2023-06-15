import streamlit as st
import pandas as pd
import os
import json
from pathlib import Path
from rdflib import Graph, URIRef, Literal, Namespace
import utils as ut





def main():
    # Set page layout to wide
    st.set_page_config(layout="wide")
    
    st.title("Hello, Streamlit!")
    st.write("Welcome to Streamlit in Colab!")
    
    # set directory information
    thisdir = Path(__file__).resolve().parent
    peopledir = thisdir / 'people'
    
    schema = Namespace("http://schema.org/")
    
    g = Graph()
    
    
    G, label_uri_dict, uri_label_dict = ut.load_knowledge_graph()
    
    #st.write(uri_label_dict)
    
    ut.get_persons(G, g)
    
    
        
    # # Create a graph object
    # graph = Graph()
    
    # # Directory path containing the JSON files
    # directory_path = peopledir
    
    # # Iterate through all files in the directory
    # for filename in os.listdir(directory_path):
    #     if filename.endswith('.json'):
    #         file_path = os.path.join(directory_path, filename)
            
    #         # Load the JSON-LD file into the graph
    #         graph.parse(file_path, format='json-ld')
    
    query_text = """
    PREFIX schema: <http://schema.org/>

    SELECT ?s ?lat ?lon
    WHERE {
    ?s a schema:Organization ;
        schema:latitude ?lat ;
        schema:longitude ?lon .
    }
    """
    results = G.query(query_text)
    coords = []
    for row in results:
        coords.append([float(row.lat), float(row.lon)])
        #st.write(coords)
        
    df = pd.DataFrame(
        coords,
        columns=['lat', 'lon'])
    
    # Create two columns
    col1, col2 = st.columns([2,1])
    
    # Add components to the first column
    with col1:
        st.header("Participants")
        ut.visualize_graph(G, g, uri_label_dict)
    
    # Add components to the second column
    with col2:
        st.header("Locations")
        st.map(df)
    
    
    
    # Iterate over the triples and print them
    #for subject, predicate, obj in G:
        #st.write(f"Subject: {subject}")
        #st.write(f"Predicate: {predicate}")
        #st.write(f"Object: {obj}")
        #st.write("------------------")
    
    

if __name__ == '__main__':
    main()