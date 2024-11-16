import streamlit as st
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import LabelEncoder
import sqlalchemy
import yaml
from yaml.loader import SafeLoader

# logo
st.markdown(
    """
    <style>
        div.stImage {
            display: flex;
            justify-content: center;
        }
    </style>
    """,
    unsafe_allow_html=True
)


logo_url = "https://i.ibb.co/HFNLLNr/thumbnail-LOGO-removebg-preview.png"
st.markdown('<div class="stImage">' + f'<img src="{logo_url}" width="350"></div>', unsafe_allow_html=True)

# Loading configuration
with open('C:/Users/Acer/Downloads/config.yml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Dictionary of users
users = config['credentials']['usernames']

# Authentication logic
def authenticate(username, password):
    user = users.get(username)
    if user and user['password'] == password:
        return user['name']
    return None

#  Session initialization 
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_name = None

# Authentication form
if not st.session_state.authenticated:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user_name = authenticate(username, password)
        if user_name:
            st.session_state.authenticated = True
            st.session_state.user_name = user_name
            st.success(f"Welcome, {user_name}!")
        else:
            st.error("Invalid username or password.")
else:
    st.success(f"Welcome back, {st.session_state.user_name}!")

# Clustering logic 
if st.session_state.authenticated:
    st.markdown("**<span style='font-size:20px;'>Clustering Analysis</span>**", unsafe_allow_html=True)
    engine = sqlalchemy.create_engine('mysql+pymysql://root:Xhh4azsese_@127.0.0.1:3306/fraude')

    if st.button("Show current detections"):
        def perform_clustering_and_display_results(engine):
            def perform_clustering_V2(data, sheet_name):
                df = pd.DataFrame(data)

                # Selecting features for clustering
                features_for_clustering = df[['Medecin', 'Gouvernorat', 'Medicament', 'Nb_Ordonnance']]

                # Encoding categorical features (w/ LabelEncoder)
                label_encoder = LabelEncoder()
                for col in ['Medecin', 'Gouvernorat', 'Medicament']:
                    features_for_clustering[col] = label_encoder.fit_transform(features_for_clustering[col])

                # Grouping by 'doctor' and aggregate features
                medecin_features = features_for_clustering.groupby('Medecin').mean()

                # KMEANS
                num_clusters = 3
                kmeans = KMeans(n_clusters=num_clusters, random_state=42)
                medecin_features['cluster'] = kmeans.fit_predict(medecin_features)

                # Converting the index of medecin_features to the same data type as 'Medecin'
                medecin_features.index = df['Medecin'].unique()

                # Merging cluster labels back to the original dataframe
                df = pd.merge(df, medecin_features[['cluster']], left_on='Medecin', right_index=True, how='left')

                result_df = df[['Medecin', 'Gouvernorat', 'cluster']].drop_duplicates()
                result_df.columns = ['Medecin', 'Gouvernorat', 'Cluster']
                result_df['Sheet'] = sheet_name  # Add a column for sheet name

                return result_df

            sheet_names = ['T1', 'T2', 'T3', 'T4']
            all_results = []

            for sheet_name in sheet_names:
                # Modifying the SQL query to retrieve data from the specific table in DB
                query = f"SELECT * FROM {sheet_name}"
                data = pd.read_sql_query(query, engine)
                result_df = perform_clustering_V2(data, sheet_name)
                all_results.append(result_df)

            # Merging the results on "Medecin" column
            merged_df = all_results[0]
            for i in range(1, len(all_results)):
                merged_df = pd.merge(merged_df, all_results[i], on=['Medecin', 'Gouvernorat'], how='outer', suffixes=('', f'_sheet_{i+1}'))

            # Creating a final table with all four columns
            final_table = pd.DataFrame({
                'Medecin': merged_df['Medecin'],
                'Gouvernorat': merged_df['Gouvernorat'],
                'Trimestre 1': merged_df['Cluster'],
                'Trimestre 2': merged_df['Cluster_sheet_2'],
                'Trimestre 3': merged_df['Cluster_sheet_3'],
                'Trimestre 4': merged_df['Cluster_sheet_4']
            })

            # Creating an empty list to store the results
            moved_medecins = []

            # Iterating through the rows of the final_table DataFrame
            for index, row in final_table.iterrows():
                # Checking if the cluster has moved from 0 to 2 in any trimester
                if (
                    (row['Trimestre 1'] == 0 and row['Trimestre 2'] == 2) or
                    (row['Trimestre 1'] == 0 and row['Trimestre 3'] == 2) or
                    (row['Trimestre 1'] == 0 and row['Trimestre 4'] == 2) or
                    (row['Trimestre 2'] == 0 and row['Trimestre 3'] == 2) or
                    (row['Trimestre 2'] == 0 and row['Trimestre 4'] == 2) or
                    (row['Trimestre 3'] == 0 and row['Trimestre 4'] == 2)
                ):
                    # Adding the "Medecin" to the list (if the condition is met)
                    moved_medecins.append({
                        'Medecin': row['Medecin'],
                        'Gouvernorat': row['Gouvernorat'],
                        'Trimestre 1': row['Trimestre 1'],
                        'Trimestre 2': row['Trimestre 2'],
                        'Trimestre 3': row['Trimestre 3'],
                        'Trimestre 4': row['Trimestre 4'],
                    })

            # Creating a DataFrame from the list of moved "Medecins"
            moved_medecins_df = pd.DataFrame(moved_medecins)

            # Printing the resulting DataFrame
            st.markdown("\n**<span style='font-size:20px;'>Les médecins à activités suspectes :</span>**\n", unsafe_allow_html=True)
            st.dataframe(moved_medecins_df, width=800, hide_index=True)

        perform_clustering_and_display_results(engine)
