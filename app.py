import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from PyPDF2 import PdfReader
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# --- Configuration de la page (Doit être la toute première commande Streamlit) ---
st.set_page_config(
    page_title="InterviewCoach AI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLE CSS PERSONNALISÉ (Pour le look "Pro") ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #FF4B4B;
        color: white;
    }
    .reportview-container {
        background: #f0f2f6;
    }
    /* Masquer le menu hamburger et le footer pour le mode "App" */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 1. CHARGEMENT DE LA CONFIGURATION ---
config_file_path = 'config.yaml'

try:
    with open(config_file_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
except FileNotFoundError:
    st.error("⚠️ Le fichier config.yaml est introuvable.")
    st.stop()

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- 2. GESTION CONNEXION / INSCRIPTION ---

if st.session_state.get("authentication_status") is not True:
    
    st.title("🔐 Accès Recruteur")
    st.markdown("Connectez-vous pour optimiser vos entretiens.")
    
    tab_login, tab_register = st.tabs(["Se connecter", "Créer un compte"])

    with tab_login:
        authenticator.login(location='main')
        if st.session_state["authentication_status"] is False:
            st.error('❌ Nom d\'utilisateur ou mot de passe incorrect')
        elif st.session_state["authentication_status"] is None:
            st.warning('Veuillez entrer vos identifiants.')

    with tab_register:
        try:
            email, username, name = authenticator.register_user(location='main')
            if email:
                st.success('✅ Compte créé ! Allez dans l\'onglet "Se connecter".')
                with open(config_file_path, 'w') as file:
                    yaml.dump(config, file, default_flow_style=False)
        except Exception as e:
            st.error(f"Erreur : {e}")

# --- 3. L'APPLICATION PRINCIPALE ---

elif st.session_state.get("authentication_status"):
    
    # Récupération infos utilisateur
    try:
        username = st.session_state['username']
        user_name = config['credentials']['usernames'][username]['name']
    except:
        user_name = "Utilisateur"

    # --- SIDEBAR (Barre latérale) ---
    with st.sidebar:
        st.title(f"👋 Bonjour, {user_name}")
        st.caption("Votre coach carrière personnel")
        st.divider()
        
        # Logout
        authenticator.logout(location='sidebar')
        st.divider()

        st.header("🎯 Objectif")
        target_role = st.text_input("Intitulé du poste visé", value="Développeur Full Stack")
        
        # NOUVEAU : Zone de texte pour l'offre d'emploi
        job_description = st.text_area("Collez l'offre d'emploi (Optionnel)", 
                                     height=150, 
                                     placeholder="Copiez ici les responsabilités et prérequis de l'annonce...")

        st.header("📄 Document")
        uploaded_file = st.file_uploader("Votre CV (PDF uniquement)", type="pdf")
        
        st.divider()
        if st.button("🗑️ Réinitialiser l'analyse"):
            st.session_state.clear()
            st.rerun()

    # --- Vérification Clé API ---
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    else:
        st.error("🚨 ERREUR : Clé API non configurée dans secrets.toml")
        st.stop()

    # --- FONCTIONS COEUR ---
    
    def extract_text_from_pdf(pdf_file):
        try:
            pdf_reader = PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            st.error(f"Erreur de lecture PDF : {e}")
            return None

    def analyze_cv_with_ai(cv_text, job_role, job_desc):
        chat = ChatOpenAI(temperature=0.5, openai_api_key=api_key, model="gpt-4o-mini")
        
        # On intègre la description du poste si elle existe
        context_job = f"Détails de l'annonce : {job_desc}" if job_desc else "Pas d'annonce spécifique fournie."

        prompt = f"""
        Tu es un Expert Recrutement Senior. Analyse ce CV pour le poste : "{job_role}".
        {context_job}
        
        CV DU CANDIDAT :
        {cv_text[:4000]}
        
        TA MISSION :
        Donne un feedback structuré et professionnel.
        
        FORMAT DE SORTIE ATTENDU (Markdown) :
        # 📊 Score de compatibilité : [Note/100]
        
        ## 🟢 Points Forts
        (Liste à puces des compétences qui matchent parfaitement)
        
        ## 🔴 Points de Vigilance
        (Ce qui manque ou ce qui est mal formulé par rapport au poste)
        
        ## 💡 Plan d'action (3 conseils)
        (3 actions concrètes pour améliorer ce CV dès maintenant)
        """
        response = chat.invoke([HumanMessage(content=prompt)])
        return response.content

    def get_interview_response(chat_history, cv_text, job_role):
        chat = ChatOpenAI(temperature=0.7, openai_api_key=api_key, model="gpt-4o-mini")
        system_prompt = f"""
        Tu es un recruteur exigeant pour le poste de {job_role}.
        Tu as lu le CV suivant : {cv_text[:2000]}.
        
        CONSIGNES :
        1. Pose UNE SEULE question à la fois.
        2. Reste professionnel mais mets le candidat au défi.
        3. Si la réponse est vague, demande des précisions.
        """
        messages = [SystemMessage(content=system_prompt)] + chat_history
        response = chat.invoke(messages)
        return response.content

    # --- INTERFACE PRINCIPALE ---
    
    st.title("🚀 InterviewCoach AI")
    st.markdown("Analysez votre CV et entraînez-vous pour votre entretien d'embauche.")

    # Init Session State
    if "analysis_result" not in st.session_state: st.session_state.analysis_result = None
    if "cv_text" not in st.session_state: st.session_state.cv_text = ""
    if "messages" not in st.session_state: st.session_state.messages = []
    if "question_count" not in st.session_state: st.session_state.question_count = 0

    if uploaded_file:
        # Lecture du PDF si pas encore fait
        if not st.session_state.cv_text:
            with st.spinner("Lecture du document..."):
                text = extract_text_from_pdf(uploaded_file)
                if text: 
                    st.session_state.cv_text = text
                    st.toast("CV chargé avec succès !", icon="✅")

        # Organisation en Onglets
        tab1, tab2 = st.tabs(["📊 Analyse & Rapport", "💬 Simulation d'Entretien"])

        # --- ONGLET 1 : ANALYSE ---
        with tab1:
            st.info(f"Analyse ciblée pour : **{target_role}**")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("Lancer l'Audit du CV"):
                    with st.spinner("L'IA examine vos compétences..."):
                        res = analyze_cv_with_ai(st.session_state.cv_text, target_role, job_description)
                        st.session_state.analysis_result = res
            
            st.divider()

            if st.session_state.analysis_result:
                st.markdown(st.session_state.analysis_result)
                
                # NOUVEAU : Bouton de téléchargement
                st.download_button(
                    label="📥 Télécharger le rapport (TXT)",
                    data=st.session_state.analysis_result,
                    file_name="Analyse_CV.txt",
                    mime="text/plain"
                )

        # --- ONGLET 2 : CHAT ---
        with tab2:
            st.caption("Le recruteur a lu votre CV. Préparez-vous.")
            
            # Initialisation du message d'accueil
            if len(st.session_state.messages) == 0:
                welcome_msg = f"Bonjour {user_name}. J'ai votre CV sous les yeux pour le poste de {target_role}. Pouvez-vous vous présenter en quelques phrases ?"
                st.session_state.messages.append(AIMessage(content=welcome_msg))

            # Affichage historique
            for msg in st.session_state.messages:
                role = "assistant" if isinstance(msg, AIMessage) else "user"
                avatar = "🤖" if role == "assistant" else "👤"
                with st.chat_message(role, avatar=avatar):
                    st.write(msg.content)

            # Zone de saisie
            if user_input := st.chat_input("Votre réponse..."):
                if st.session_state.question_count >= 10: # J'ai augmenté à 10 pour le test
                    st.warning("⛔ La version démo est limitée à 10 échanges.")
                else:
                    # User message
                    st.session_state.messages.append(HumanMessage(content=user_input))
                    with st.chat_message("user", avatar="👤"):
                        st.write(user_input)
                    
                    # AI Response
                    with st.chat_message("assistant", avatar="🤖"):
                        with st.spinner("Le recruteur prend des notes..."):
                            resp = get_interview_response(st.session_state.messages, st.session_state.cv_text, target_role)
                            st.write(resp)
                    
                    st.session_state.messages.append(AIMessage(content=resp))
                    st.session_state.question_count += 1

    else:
        # Écran d'accueil quand aucun fichier n'est là
        st.info("👈 Pour commencer, veuillez charger votre CV (PDF) dans le menu de gauche.")
        st.image("https://cdn.pixabay.com/photo/2018/03/30/02/33/desk-3274297_1280.jpg", use_container_width=True, caption="Prêt à décrocher le job ?")