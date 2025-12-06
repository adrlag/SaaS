import streamlit as st
from supabase import create_client, Client
from typing import Optional
import pandas as pd
from datetime import datetime
import plotly.express as px
from fpdf import FPDF
import requests
from io import BytesIO

# Configuración de la página
st.set_page_config(
    page_title="Panel de Administración",
    page_icon=None,
    layout="wide"
)

# Catálogo de materiales
MATERIALES = {
    "Gas Refrigerante": 25.0,
    "Materiales Varios": 15.0,
    "Tubería PVC 20mm": 8.50,
    "Válvula de Compresión": 12.0,
    "Aislamiento Térmico": 5.0,
    "Cable Eléctrico": 3.50
}

# Catálogo de servicios
SERVICIOS = {
    "Mano de Obra 1h": 45.0,
    "Desplazamiento": 30.0,
    "Revisión Técnica": 50.0,
    "Reparación Urgente": 60.0,
    "Instalación": 80.0,
    "Mantenimiento Preventivo": 55.0
}

# Inicializar variables de sesión
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'supabase' not in st.session_state:
    st.session_state.supabase = None
if 'organization_id' not in st.session_state:
    st.session_state.organization_id = None
if 'temp_items' not in st.session_state:
    st.session_state.temp_items = []


def init_supabase_client() -> Optional[Client]:
    """Inicializa el cliente de Supabase con las credenciales públicas"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"Error de configuración: Falta {e} en st.secrets")
        st.stop()
        return None


def get_authenticated_client() -> Optional[Client]:
    """Obtiene el cliente de Supabase autenticado con el token de sesión"""
    if not st.session_state.supabase:
        st.session_state.supabase = init_supabase_client()
    
    if st.session_state.authenticated and st.session_state.user:
        # El cliente ya tiene la sesión configurada después del login
        return st.session_state.supabase
    
    return None


def login(email: str, password: str) -> bool:
    """Autentica al usuario y configura la sesión"""
    try:
        supabase = init_supabase_client()
        
        # Autenticar usuario
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Guardar sesión
            st.session_state.user = response.user
            st.session_state.authenticated = True
            
            # Configurar el cliente con el token de sesión
            # Esto es crítico para que RLS funcione correctamente
            session_token = response.session.access_token
            supabase.auth.set_session(
                access_token=session_token,
                refresh_token=response.session.refresh_token
            )
            st.session_state.supabase = supabase
            
            # Obtener el organization_id del perfil del usuario
            fetch_organization_id()
            
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"Error en el login: {str(e)}")
        return False


def fetch_organization_id():
    """Obtiene el organization_id del perfil del usuario autenticado"""
    try:
        supabase = get_authenticated_client()
        if not supabase:
            return
        
        # Obtener el perfil del usuario actual
        user_id = st.session_state.user.id
        response = supabase.table('profiles').select('organization_id').eq('id', user_id).execute()
        
        if response.data and len(response.data) > 0:
            st.session_state.organization_id = response.data[0]['organization_id']
        else:
            st.error("No se encontró el perfil del usuario")
            
    except Exception as e:
        st.error(f"Error al obtener organization_id: {str(e)}")


def logout():
    """Cierra la sesión del usuario"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.supabase = None
    st.session_state.organization_id = None
    st.rerun()


def show_login_page():
    """Muestra la página de login"""
    st.title("Panel de Administración")
    st.subheader("Iniciar Sesión")
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Iniciar Sesión", use_container_width=True)
        
        if submit:
            if email and password:
                with st.spinner("Iniciando sesión..."):
                    if login(email, password):
                        st.success("Sesión iniciada correctamente")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
            else:
                st.warning("Completa todos los campos")


def show_sidebar():
    """Muestra el sidebar con navegación y logout"""
    with st.sidebar:
        st.title("Administración")
        
        if st.session_state.user:
            st.caption(st.session_state.user.email)
        
        st.divider()
        
        page = st.radio(
            "Navegación",
            ["Dashboard", "Crear Parte", "Partes de Trabajo", "Detalles de un Parte", "Mi Empresa", "Business Intelligence"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        if st.button("Cerrar Sesión", use_container_width=True):
            logout()
        
        return page


def show_dashboard():
    """Muestra el dashboard con métricas clave"""
    st.title("Dashboard")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    try:
        org_id = st.session_state.organization_id
        
        # Obtener métricas
        # Total Clientes
        clients_response = supabase.table('clients').select('id', count='exact').eq('organization_id', org_id).execute()
        total_clients = clients_response.count if hasattr(clients_response, 'count') else len(clients_response.data)
        
        # Partes Abiertos (status != closed)
        open_orders_response = supabase.table('work_orders').select('id', count='exact').eq('organization_id', org_id).neq('status', 'closed').execute()
        open_orders = open_orders_response.count if hasattr(open_orders_response, 'count') else len(open_orders_response.data)
        
        # Partes Cerrados
        closed_orders_response = supabase.table('work_orders').select('id', count='exact').eq('organization_id', org_id).eq('status', 'closed').execute()
        closed_orders = closed_orders_response.count if hasattr(closed_orders_response, 'count') else len(closed_orders_response.data)
        
        # Mostrar métricas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Clientes", total_clients)
        
        with col2:
            st.metric("Partes Abiertos", open_orders)
        
        with col3:
            st.metric("Partes Cerrados", closed_orders)
        
    except Exception as e:
        st.error(f"Error al cargar métricas: {str(e)}")


def show_clients_page():
    """Muestra la página de gestión de clientes"""
    st.title("Clientes")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    # Formulario para añadir nuevo cliente
    with st.expander("Añadir Nuevo Cliente", expanded=False):
        with st.form("new_client_form"):
            name = st.text_input("Nombre del Cliente *")
            address = st.text_area("Dirección")
            phone = st.text_input("Teléfono")
            submit = st.form_submit_button("Crear Cliente", use_container_width=True)
            
            if submit:
                if name:
                    try:
                        response = supabase.table('clients').insert({
                            'name': name,
                            'address': address if address else None,
                            'phone': phone if phone else None,
                            'organization_id': org_id
                        }).execute()
                        
                        if response.data:
                            st.success(f"Cliente '{name}' creado exitosamente!")
                            st.rerun()
                        else:
                            st.error("Error al crear el cliente")
                    except Exception as e:
                        st.error(f"Error al crear cliente: {str(e)}")
                else:
                    st.warning("El nombre es obligatorio")
    
    st.divider()
    
    # Lista de clientes
    st.subheader("Lista de Clientes")
    
    try:
        response = supabase.table('clients').select('*').eq('organization_id', org_id).order('name').execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            # Reordenar columnas para mejor visualización
            if 'id' in df.columns:
                df = df[['name', 'address', 'phone', 'id']]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay clientes registrados aún")
            
    except Exception as e:
        st.error(f"Error al cargar clientes: {str(e)}")


def show_create_work_order_page():
    """Vista exclusiva para crear nuevos partes de trabajo"""
    st.title("Crear Parte de Trabajo")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    # Inicializar temp_items si no existe
    if 'temp_items' not in st.session_state:
        st.session_state.temp_items = []
    
    try:
        # Obtener lista de clientes
        clients_response = supabase.table('clients').select('id, name').eq('organization_id', org_id).order('name').execute()
        clients_list = clients_response.data if clients_response.data else []
        
        # Obtener lista de técnicos (profiles de la organización)
        technicians_response = supabase.table('profiles').select('id, full_name').eq('organization_id', org_id).order('full_name').execute()
        technicians_list = technicians_response.data if technicians_response.data else []
        
        # Obtener el usuario actual como técnico por defecto
        current_user_id = st.session_state.user.id if st.session_state.user else None
        current_technician = None
        if current_user_id and technicians_list:
            for tech in technicians_list:
                if tech['id'] == current_user_id:
                    current_technician = tech
                    break
        
        if not clients_list:
            st.warning("No hay clientes registrados. Crea al menos un cliente primero.")
            st.info("Ve a la sección 'Clientes' para crear uno nuevo.")
        else:
            # Sección 1: Datos del Trabajo
            st.markdown("### Datos del Trabajo")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                client_options = {client['name']: client['id'] for client in clients_list}
                selected_client_name = st.selectbox(
                    "Cliente",
                    options=list(client_options.keys()),
                    index=0 if client_options else None,
                    key="create_client_select"
                )
                selected_client_id = client_options.get(selected_client_name) if selected_client_name else None
                
                description = st.text_area(
                    "Descripción",
                    placeholder="Describe el trabajo a realizar...",
                    height=80,
                    key="create_description"
                )
            
            with col2:
                st.caption("Fecha: " + datetime.now().strftime("%d/%m/%Y"))
                if current_technician:
                    st.caption(f"Técnico: {current_technician['full_name']}")
                else:
                    st.caption("Técnico: Sin asignar")
            
            st.divider()
            
            # Sección 2: Detalles de un Parte
            st.markdown("### Detalles de un Parte")
            
            col_mat, col_serv = st.columns(2)
            
            with col_mat:
                st.markdown("**Materiales**")
                
                # Selector de materiales
                materiales_options = list(MATERIALES.keys())
                materiales_options.insert(0, "Seleccionar material...")
                selected_material = st.selectbox(
                    "Material",
                    options=materiales_options,
                    index=0,
                    key="create_material_select"
                )
                
                if selected_material and selected_material != "Seleccionar material...":
                    material_price_default = MATERIALES[selected_material]
                    
                    material_quantity = st.number_input(
                        "Cantidad",
                        min_value=0.01,
                        value=1.0,
                        step=0.01,
                        key="create_material_quantity"
                    )
                    
                    material_price = st.number_input(
                        "Precio por Unidad (€)",
                        min_value=0.0,
                        value=float(material_price_default),
                        step=0.01,
                        key="create_material_price"
                    )
                    
                    if st.button("Añadir Material", key="create_add_material", use_container_width=True, type="primary"):
                        new_item = {
                            'concept': selected_material,
                            'quantity': float(material_quantity),
                            'price': float(material_price)
                        }
                        st.session_state.temp_items.append(new_item)
                        st.rerun()
            
            with col_serv:
                st.markdown("**Servicios**")
                
                # Selector de servicios
                servicios_options = list(SERVICIOS.keys())
                servicios_options.insert(0, "Seleccionar servicio...")
                selected_service = st.selectbox(
                    "Servicio",
                    options=servicios_options,
                    index=0,
                    key="create_service_select"
                )
                
                if selected_service and selected_service != "Seleccionar servicio...":
                    service_price_default = SERVICIOS[selected_service]
                    
                    service_quantity = st.number_input(
                        "Cantidad",
                        min_value=0.01,
                        value=1.0,
                        step=0.01,
                        key="create_service_quantity"
                    )
                    
                    service_price = st.number_input(
                        "Precio por Unidad (€)",
                        min_value=0.0,
                        value=float(service_price_default),
                        step=0.01,
                        key="create_service_price"
                    )
                    
                    if st.button("Añadir Servicio", key="create_add_service", use_container_width=True, type="primary"):
                        new_item = {
                            'concept': selected_service,
                            'quantity': float(service_quantity),
                            'price': float(service_price)
                        }
                        st.session_state.temp_items.append(new_item)
                        st.rerun()
            
            st.divider()
            
            # Añadir personalizado
            with st.expander("Añadir Concepto Personalizado", expanded=False):
                with st.form("create_custom_item_form", clear_on_submit=True):
                    custom_concept = st.text_input("Concepto", placeholder="Ej: Material especial o servicio personalizado", key="create_custom_concept")
                    custom_col1, custom_col2 = st.columns(2)
                    
                    with custom_col1:
                        custom_quantity = st.number_input("Cantidad", min_value=0.01, value=1.0, step=0.01, key="create_custom_quantity")
                    
                    with custom_col2:
                        custom_price = st.number_input("Precio (€)", min_value=0.0, value=0.0, step=0.01, key="create_custom_price")
                    
                    add_custom = st.form_submit_button("Añadir", use_container_width=True, type="primary")
                    
                    if add_custom:
                        if custom_concept and custom_concept.strip():
                            new_item = {
                                'concept': custom_concept.strip(),
                                'quantity': float(custom_quantity),
                                'price': float(custom_price)
                            }
                            st.session_state.temp_items.append(new_item)
                            st.rerun()
                        else:
                            st.warning("Introduce un concepto")
            
            st.divider()
            
            # Sección 3: Resumen y Guardado
            st.markdown("### Resumen")
            
            if st.session_state.temp_items:
                # Mostrar cada item con botón de eliminar
                for idx, item in enumerate(st.session_state.temp_items):
                    total_linea = item['quantity'] * item['price']
                    
                    col_concept, col_qty, col_price, col_total, col_action = st.columns([3.5, 1, 1.5, 1.5, 0.5])
                    
                    with col_concept:
                        st.write(f"**{item['concept']}**")
                    
                    with col_qty:
                        st.caption(f"{item['quantity']:.2f}")
                    
                    with col_price:
                        st.caption(f"{item['price']:.2f} €")
                    
                    with col_total:
                        st.caption(f"**{total_linea:.2f} €**")
                    
                    with col_action:
                        st.markdown("<style>div[data-testid='stButton'] > button {width: 100%; padding: 0.25rem 0.5rem; font-size: 0.875rem;}</style>", unsafe_allow_html=True)
                        if st.button("🗑️", key=f"delete_item_{idx}", use_container_width=True, type="secondary", help="Eliminar"):
                            st.session_state.temp_items.pop(idx)
                            st.rerun()
                    
                    st.divider()
                
                # Mostrar tabla resumen también (opcional, para referencia)
                items_df = pd.DataFrame(st.session_state.temp_items)
                items_df['Total Línea'] = items_df['quantity'] * items_df['price']
                
                display_df = items_df[['concept', 'quantity', 'price', 'Total Línea']].copy()
                display_df.columns = ['Concepto', 'Unidades', 'Precio por Unidad', 'Precio Total']
                
                with st.expander("Ver tabla resumen", expanded=False):
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Concepto": st.column_config.TextColumn("Concepto", width="large"),
                            "Unidades": st.column_config.NumberColumn("Unidades", width="small", format="%.2f"),
                            "Precio por Unidad": st.column_config.NumberColumn("Precio por Unidad (€)", width="medium", format="%.2f"),
                            "Precio Total": st.column_config.NumberColumn("Precio Total (€)", width="medium", format="%.2f")
                        }
                    )
                
                total = items_df['Total Línea'].sum()
                
                col_total1, col_total2, col_total3 = st.columns([1, 2, 1])
                with col_total2:
                    st.metric("Total del Parte", f"{total:.2f} €")
                
                col_action1, col_action2, col_action3 = st.columns([1, 2, 1])
                
                with col_action2:
                    if st.button("Limpiar Todo", use_container_width=True, type="secondary", key="create_clear_all"):
                        st.session_state.temp_items = []
                        st.rerun()
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    save_all = st.button(
                        "Guardar Parte",
                        use_container_width=True,
                        type="primary",
                        key="create_save_all"
                    )
                    
                    if save_all:
                        if not selected_client_id:
                            st.error("Selecciona un cliente")
                        elif not st.session_state.temp_items:
                            st.error("Añade al menos un material o servicio")
                        else:
                            try:
                                with st.spinner("Guardando..."):
                                    work_order_data = {
                                        'client_id': selected_client_id,
                                        'status': 'draft',
                                        'description_summary': description if description else None,
                                        'organization_id': org_id
                                    }
                                    
                                    if current_technician:
                                        work_order_data['technician_id'] = current_technician['id']
                                    
                                    work_order_response = supabase.table('work_orders').insert(work_order_data).execute()
                                    
                                    if not work_order_response.data:
                                        st.error("Error al crear la cabecera del parte")
                                    else:
                                        new_work_order_id = work_order_response.data[0]['id']
                                        
                                        items_to_insert = []
                                        for item in st.session_state.temp_items:
                                            items_to_insert.append({
                                                'work_order_id': new_work_order_id,
                                                'concept': str(item['concept']),
                                                'quantity': float(item['quantity']),
                                                'price': float(item['price'])
                                            })
                                        
                                        if items_to_insert:
                                            items_response = supabase.table('work_order_items').insert(items_to_insert).execute()
                                            
                                            if items_response.data:
                                                st.session_state.temp_items = []
                                                st.success(f"Parte guardado correctamente (ID: {new_work_order_id})")
                                                st.info("Puedes ver el parte en la sección 'Partes de Trabajo'")
                                                st.rerun()
                                            else:
                                                st.error("Error al guardar los items")
                                        else:
                                            st.session_state.temp_items = []
                                            st.success(f"Parte guardado correctamente (ID: {new_work_order_id})")
                                            st.rerun()
                            
                            except Exception as e:
                                st.error(f"Error al guardar: {str(e)}")
            else:
                st.caption("Añade materiales o servicios usando los botones rápidos o el formulario manual")
    
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        st.exception(e)


def show_work_orders_page():
    """Muestra la página de gestión de partes de trabajo"""
    st.title("Partes de Trabajo")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    st.info("Para crear un nuevo parte, ve a la sección 'Crear Parte' en el menú lateral.")
    
    st.divider()
    
    # Filtro por estado
    col1, col2 = st.columns([1, 4])
    with col1:
        status_filter = st.selectbox(
            "Filtrar por Estado",
            ["Todos", "draft", "signed", "closed"],
            label_visibility="collapsed"
        )
    
    try:
        # Construir query base
        query = supabase.table('work_orders').select('id, status, description_summary, client_id, technician_id, created_at').eq('organization_id', org_id)
        
        # Aplicar filtro de estado
        if status_filter != "Todos":
            query = query.eq('status', status_filter)
        
        response = query.order('id', desc=True).execute()
        
        if response.data:
            # Obtener IDs únicos de clientes y técnicos
            client_ids = [order.get('client_id') for order in response.data if order.get('client_id')]
            technician_ids = [order.get('technician_id') for order in response.data if order.get('technician_id')]
            
            # Obtener nombres de clientes
            clients_dict = {}
            if client_ids:
                clients_response = supabase.table('clients').select('id, name').in_('id', list(set(client_ids))).execute()
                clients_dict = {client['id']: client['name'] for client in clients_response.data}
            
            # Obtener nombres de técnicos
            technicians_dict = {}
            if technician_ids:
                technicians_response = supabase.table('profiles').select('id, full_name').in_('id', list(set(technician_ids))).execute()
                technicians_dict = {tech['id']: tech['full_name'] for tech in technicians_response.data}
            
            # Procesar datos para la tabla
            orders_data = []
            for order in response.data:
                client_id = order.get('client_id')
                technician_id = order.get('technician_id')
                created_at = order.get('created_at', '')
                
                # Formatear fecha
                fecha = ''
                if created_at:
                    try:
                        fecha = created_at[:10] if len(created_at) >= 10 else created_at
                    except:
                        fecha = ''
                
                orders_data.append({
                    'ID': str(order.get('id', '')),
                    'Fecha': fecha,
                    'Cliente': clients_dict.get(client_id, 'N/A') if client_id else 'N/A',
                    'Técnico': technicians_dict.get(technician_id, 'N/A') if technician_id else 'N/A',
                    'Estado': order.get('status', ''),
                    'Resumen': order.get('description_summary', '') or ''
                })
            
            df = pd.DataFrame(orders_data)
            
            # Guardar datos originales en session_state para comparar cambios
            session_key = f"work_orders_original_{org_id}"
            editor_key = f"work_orders_editor_{org_id}"
            
            # Inicializar datos originales si no existen
            if session_key not in st.session_state:
                st.session_state[session_key] = df.copy()
            
            original_df = st.session_state[session_key]
            
            # Mostrar tabla editable
            st.subheader("Lista de Partes de Trabajo")
            st.caption("Modifica el estado en la tabla. Los cambios se guardan automáticamente.")
            
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                disabled=["ID", "Fecha", "Cliente", "Técnico", "Resumen"],
                column_config={
                    "ID": st.column_config.TextColumn("ID", width="small"),
                    "Fecha": st.column_config.DateColumn("Fecha", width="small"),
                    "Cliente": st.column_config.TextColumn("Cliente"),
                    "Técnico": st.column_config.TextColumn("Técnico"),
                    "Estado": st.column_config.SelectboxColumn(
                        "Estado",
                        options=["draft", "signed", "closed"],
                        width="small",
                        required=True
                    ),
                    "Resumen": st.column_config.TextColumn("Resumen", width="large")
                },
                key=editor_key
            )
            
            # Detectar y guardar cambios automáticamente
            # Comparar estado por estado usando el ID como referencia
            if len(edited_df) == len(original_df):
                changes_detected = False
                updates_pending = []
                
                # Crear un diccionario de IDs para comparación más eficiente
                original_dict = {row['ID']: row['Estado'] for _, row in original_df.iterrows()}
                
                for idx, row in edited_df.iterrows():
                    work_order_id = row['ID']
                    new_status = row['Estado']
                    original_status = original_dict.get(work_order_id)
                    
                    if original_status and new_status != original_status:
                        changes_detected = True
                        updates_pending.append({
                            'id': work_order_id,
                            'status': new_status
                        })
                
                # Si hay cambios, guardarlos automáticamente
                if changes_detected and updates_pending:
                    success_count = 0
                    error_messages = []
                    
                    for update in updates_pending:
                        try:
                            update_response = supabase.table('work_orders').update({
                                'status': update['status']
                            }).eq('id', update['id']).eq('organization_id', org_id).execute()
                            
                            if update_response.data:
                                success_count += 1
                            else:
                                error_messages.append(f"Parte {update['id']}")
                        except Exception as e:
                            error_messages.append(f"Parte {update['id']}: {str(e)}")
                    
                    # Mostrar feedback
                    if success_count > 0:
                        st.success(f"{success_count} parte(s) actualizado(s) automáticamente")
                    
                    if error_messages:
                        for error_msg in error_messages:
                            st.error(f"Error al actualizar {error_msg}")
                    
                    # Actualizar datos originales y recargar
                    if success_count > 0:
                        st.session_state[session_key] = edited_df.copy()
                        st.rerun()
            
            # Actualizar datos originales si la estructura cambió (nuevos registros o eliminados)
            if len(edited_df) != len(original_df):
                st.session_state[session_key] = df.copy()
        else:
            st.info("No hay partes de trabajo registrados aún")
            
    except Exception as e:
        st.error(f"Error al cargar partes de trabajo: {str(e)}")
        st.exception(e)


def show_bi_page():
    """Muestra la página de Business Intelligence con KPIs y visualizaciones"""
    st.title("Business Intelligence")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    try:
        # 1. INGRESOS TOTALES POR MES
        st.subheader("Ingresos Totales por Mes")
        
        # Obtener work_orders con fechas de creación
        work_orders_response = supabase.table('work_orders').select('id, created_at').eq('organization_id', org_id).execute()
        
        if work_orders_response.data:
            work_order_ids = [wo['id'] for wo in work_orders_response.data]
            
            # Obtener work_order_items con cantidad y precio
            work_order_items_response = supabase.table('work_order_items').select('work_order_id, quantity, price').in_('work_order_id', work_order_ids).execute()
            
            if work_order_items_response.data:
                # Crear DataFrame con los items
                items_df = pd.DataFrame(work_order_items_response.data)
                
                # Crear DataFrame con work_orders y sus fechas
                orders_df = pd.DataFrame(work_orders_response.data)
                orders_df['created_at'] = pd.to_datetime(orders_df['created_at'])
                
                # Merge para obtener las fechas
                merged_df = items_df.merge(orders_df, left_on='work_order_id', right_on='id', how='left')
                
                # Filtrar por organization_id (seguridad adicional)
                merged_df = merged_df[merged_df['work_order_id'].isin(work_order_ids)]
                
                # Calcular ingresos (cantidad * precio)
                merged_df['ingresos'] = merged_df['quantity'] * merged_df['price']
                
                # Agrupar por mes
                merged_df['mes'] = merged_df['created_at'].dt.to_period('M').astype(str)
                ingresos_por_mes = merged_df.groupby('mes')['ingresos'].sum().reset_index()
                ingresos_por_mes = ingresos_por_mes.sort_values('mes')
                
                if not ingresos_por_mes.empty:
                    # Crear gráfico de barras
                    fig_ingresos = px.bar(
                        ingresos_por_mes,
                        x='mes',
                        y='ingresos',
                        title='Ingresos Totales por Mes',
                        labels={'mes': 'Mes', 'ingresos': 'Ingresos (€)'},
                        color='ingresos',
                        color_continuous_scale='Blues'
                    )
                    fig_ingresos.update_layout(
                        xaxis_title="Mes",
                        yaxis_title="Ingresos (€)",
                        showlegend=False,
                        height=400
                    )
                    st.plotly_chart(fig_ingresos, use_container_width=True)
                else:
                    st.info("No hay datos de ingresos disponibles para mostrar")
            else:
                st.info("No hay items de partes de trabajo registrados aún")
        else:
            st.info("No hay partes de trabajo registrados aún")
        
        st.divider()
        
        # 2. TOP CLIENTES
        st.subheader("Top 5 Clientes por Partes Generados")
        
        # Obtener work_orders con client_id
        top_clients_response = supabase.table('work_orders').select('client_id').eq('organization_id', org_id).execute()
        
        if top_clients_response.data:
            # Crear DataFrame y contar por cliente
            clients_count_df = pd.DataFrame(top_clients_response.data)
            clients_count_df = clients_count_df[clients_count_df['client_id'].notna()]
            
            if not clients_count_df.empty:
                # Contar partes por cliente
                client_counts = clients_count_df['client_id'].value_counts().head(5).reset_index()
                client_counts.columns = ['client_id', 'num_partes']
                
                # Obtener nombres de clientes
                client_ids = client_counts['client_id'].tolist()
                clients_info_response = supabase.table('clients').select('id, name').in_('id', client_ids).eq('organization_id', org_id).execute()
                
                if clients_info_response.data:
                    clients_dict = {client['id']: client['name'] for client in clients_info_response.data}
                    client_counts['nombre_cliente'] = client_counts['client_id'].map(clients_dict)
                    client_counts = client_counts[client_counts['nombre_cliente'].notna()]
                    
                    if not client_counts.empty:
                        # Ordenar por número de partes (ascendente para gráfico horizontal)
                        client_counts = client_counts.sort_values('num_partes', ascending=True)
                        
                        # Crear gráfico horizontal
                        fig_clientes = px.bar(
                            client_counts,
                            x='num_partes',
                            y='nombre_cliente',
                            orientation='h',
                            title='Top 5 Clientes por Número de Partes',
                            labels={'num_partes': 'Número de Partes', 'nombre_cliente': 'Cliente'},
                            color='num_partes',
                            color_continuous_scale='Greens'
                        )
                        fig_clientes.update_layout(
                            xaxis_title="Número de Partes",
                            yaxis_title="Cliente",
                            showlegend=False,
                            height=400
                        )
                        st.plotly_chart(fig_clientes, use_container_width=True)
                    else:
                        st.info("No se encontraron nombres de clientes para los datos disponibles")
                else:
                    st.info("No se encontró información de los clientes")
            else:
                st.info("No hay partes de trabajo asociados a clientes")
        else:
            st.info("No hay partes de trabajo registrados aún")
        
        st.divider()
        
        # 3. EFICIENCIA TÉCNICA
        st.subheader("Eficiencia Técnica")
        
        # Obtener work_orders con técnicos y tiempos
        efficiency_response = supabase.table('work_orders').select('id, technician_id, start_time, end_time').eq('organization_id', org_id).execute()
        
        if efficiency_response.data:
            efficiency_df = pd.DataFrame(efficiency_response.data)
            efficiency_df = efficiency_df[efficiency_df['technician_id'].notna()]
            
            if not efficiency_df.empty:
                # Obtener nombres de técnicos
                technician_ids = efficiency_df['technician_id'].unique().tolist()
                technicians_info_response = supabase.table('profiles').select('id, full_name').in_('id', technician_ids).execute()
                
                technicians_dict = {}
                if technicians_info_response.data:
                    technicians_dict = {tech['id']: tech['full_name'] for tech in technicians_info_response.data}
                
                # Procesar datos de eficiencia
                efficiency_data = []
                
                for tech_id in efficiency_df['technician_id'].unique():
                    tech_orders = efficiency_df[efficiency_df['technician_id'] == tech_id]
                    
                    # Contar partes
                    num_partes = len(tech_orders)
                    
                    # Calcular tiempo promedio si hay start_time y end_time
                    tiempos = []
                    for _, order in tech_orders.iterrows():
                        if pd.notna(order.get('start_time')) and pd.notna(order.get('end_time')):
                            try:
                                start = pd.to_datetime(order['start_time'])
                                end = pd.to_datetime(order['end_time'])
                                if start < end:  # Validar que el tiempo sea lógico
                                    tiempo_minutos = (end - start).total_seconds() / 60
                                    tiempos.append(tiempo_minutos)
                            except:
                                pass
                    
                    tiempo_promedio = sum(tiempos) / len(tiempos) if tiempos else None
                    
                    # Formatear tiempo promedio
                    tiempo_formato = None
                    if tiempo_promedio:
                        if tiempo_promedio >= 60:
                            horas = int(tiempo_promedio // 60)
                            minutos = int(tiempo_promedio % 60)
                            tiempo_formato = f"{horas}h {minutos}m"
                        else:
                            tiempo_formato = f"{int(tiempo_promedio)}m"
                    
                    efficiency_data.append({
                        'Técnico': technicians_dict.get(tech_id, f'Técnico {str(tech_id)[:8]}'),
                        'Número de Partes': num_partes,
                        'Tiempo Promedio': tiempo_formato if tiempo_formato else 'N/A',
                        'Partes con Tiempo Registrado': len(tiempos)
                    })
                
                if efficiency_data:
                    efficiency_result_df = pd.DataFrame(efficiency_data)
                    efficiency_result_df = efficiency_result_df.sort_values('Número de Partes', ascending=False)
                    
                    # Mostrar tabla
                    st.dataframe(
                        efficiency_result_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Técnico": st.column_config.TextColumn("Técnico", width="medium"),
                            "Número de Partes": st.column_config.NumberColumn("Número de Partes", width="small"),
                            "Tiempo Promedio": st.column_config.TextColumn("Tiempo Promedio", width="medium"),
                            "Partes con Tiempo Registrado": st.column_config.NumberColumn("Partes con Tiempo", width="small")
                        }
                    )
                else:
                    st.info("No hay datos de eficiencia disponibles")
            else:
                st.info("No hay partes de trabajo asignados a técnicos")
        else:
            st.info("No hay partes de trabajo registrados aún")
        
    except Exception as e:
        st.error(f"Error al cargar datos de Business Intelligence: {str(e)}")
        st.exception(e)


def create_work_order_pdf(work_order_id: str, supabase: Client, org_id: str) -> bytes:
    """Genera un PDF del parte de trabajo y lo devuelve como bytes"""
    
    # Obtener datos del parte
    work_order_response = supabase.table('work_orders').select(
        'id, created_at, client_id, technician_id, status, description_summary'
    ).eq('id', work_order_id).eq('organization_id', org_id).execute()
    
    if not work_order_response.data:
        raise ValueError("Parte de trabajo no encontrado")
    
    work_order = work_order_response.data[0]
    client_id = work_order.get('client_id')
    
    # Obtener datos del cliente
    if client_id:
        client_response = supabase.table('clients').select('name, address, phone').eq('id', client_id).execute()
        if client_response.data:
            client_data = client_response.data[0]
            client_name = client_data.get('name', 'Sin cliente')
            client_address = client_data.get('address', '')
            client_phone = client_data.get('phone', '')
            client_nif = 'NIF no especificado'  # Campo no disponible en la BD
        else:
            client_name = 'Sin cliente'
            client_address = ''
            client_phone = ''
            client_nif = 'NIF no especificado'
    else:
        client_name = 'Sin cliente'
        client_address = ''
        client_phone = ''
        client_nif = 'NIF no especificado'
    
    # Obtener items del parte
    items_response = supabase.table('work_order_items').select(
        'concept, quantity, price'
    ).eq('work_order_id', work_order_id).order('created_at').execute()
    
    items = items_response.data if items_response.data else []
    
    # Obtener datos de la organización
    org_logo_url = None
    try:
        org_response = supabase.table('organizations').select('name, address, cif, logo_url').eq('id', org_id).execute()
        if org_response.data:
            org_data = org_response.data[0]
            org_name = org_data.get('name', 'Mi Empresa')
            org_address = org_data.get('address', 'Dirección no especificada')
            org_cif = org_data.get('cif', 'CIF no especificado')
            org_logo_url = org_data.get('logo_url')
        else:
            org_name = "Mi Empresa"
            org_address = "Dirección no especificada"
            org_cif = "CIF no especificado"
    except:
        # Si no existe la tabla organizations, usar valores por defecto
        org_name = "Mi Empresa"
        org_address = "Dirección no especificada"
        org_cif = "CIF no especificado"
    
    # Intentar obtener logo_url por separado si no se obtuvo antes
    if not org_logo_url:
        try:
            logo_response = supabase.table('organizations').select('logo_url').eq('id', org_id).execute()
            if logo_response.data and logo_response.data[0].get('logo_url'):
                org_logo_url = logo_response.data[0].get('logo_url')
        except:
            org_logo_url = None
    
    # Fecha formateada
    created_at = work_order.get('created_at', '')
    if created_at:
        try:
            fecha_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            fecha_str = fecha_obj.strftime('%d/%m/%Y')
        except:
            fecha_str = created_at[:10] if len(created_at) >= 10 else 'Sin fecha'
    else:
        fecha_str = 'Sin fecha'
    
    # Estado
    status = work_order.get('status', 'draft')
    status_display = {
        'draft': 'Borrador',
        'signed': 'Firmado',
        'closed': 'Cerrado'
    }
    status_str = status_display.get(status, status)
    
    # Crear PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Configurar fuente (Latin-1 compatible)
    pdf.set_font('Arial', 'B', 16)
    
    # ===== CABECERA =====
    # Columna izquierda: Datos de mi empresa
    pdf.set_xy(10, 10)
    
    # Intentar incluir el logo si existe
    logo_included = False
    if org_logo_url:
        try:
            # Descargar la imagen del logo
            response = requests.get(org_logo_url, timeout=5)
            if response.status_code == 200:
                # Guardar imagen en memoria
                logo_image = BytesIO(response.content)
                
                # Incrustar logo en el PDF (tamaño 25x25mm, posición 10,10)
                pdf.image(logo_image, x=10, y=10, w=25, h=25)
                logo_included = True
        except Exception as logo_error:
            # Si falla la descarga del logo, continuar sin él
            pass
    
    # Si no hay logo, mostrar placeholder
    if not logo_included:
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(200, 200, 200)
        pdf.cell(25, 5, "[LOGO]", 0, 0)
        pdf.set_text_color(0, 0, 0)
    
    # Datos de la empresa (ajustar posición si hay logo)
    y_start_text = 10 if not logo_included else 37
    pdf.set_xy(10, y_start_text)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(90, 8, org_name.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.set_x(10)
    pdf.cell(90, 5, org_address.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.set_x(10)
    pdf.cell(90, 5, f"CIF: {org_cif}", 0, 1)
    
    # Columna derecha: Datos del cliente y documento
    pdf.set_xy(110, 10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(90, 6, "CLIENTE", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.set_x(110)
    pdf.cell(90, 5, client_name.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    if client_address:
        pdf.set_x(110)
        pdf.cell(90, 5, client_address.encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    if client_phone:
        pdf.set_x(110)
        pdf.cell(90, 5, f"Tel: {client_phone}", 0, 1)
    pdf.set_x(110)
    pdf.cell(90, 5, f"NIF: {client_nif}", 0, 1)
    
    # Datos del documento
    pdf.set_xy(110, pdf.get_y() + 5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(90, 6, "DOCUMENTO", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.set_x(110)
    pdf.cell(90, 5, f"Nº Parte: {str(work_order_id)[:8]}", 0, 1)
    pdf.set_x(110)
    pdf.cell(90, 5, f"Fecha: {fecha_str}", 0, 1)
    pdf.set_x(110)
    pdf.cell(90, 5, f"Estado: {status_str}", 0, 1)
    
    # Línea separadora
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y() + 5, 200, pdf.get_y() + 5)
    y_start_table = pdf.get_y() + 10
    
    # ===== CUERPO: TABLA DE ITEMS =====
    pdf.set_y(y_start_table)
    pdf.set_font('Arial', 'B', 10)
    
    # Cabecera de tabla con fondo gris
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(100, 8, "Concepto", 1, 0, 'L', True)
    pdf.cell(25, 8, "Cantidad", 1, 0, 'R', True)
    pdf.cell(30, 8, "Precio Unit.", 1, 0, 'R', True)
    pdf.cell(35, 8, "Total", 1, 1, 'R', True)
    
    pdf.set_fill_color(255, 255, 255)
    pdf.set_font('Arial', '', 10)
    
    subtotal = 0
    for item in items:
        concept = str(item.get('concept', ''))
        quantity = float(item.get('quantity', 0))
        price = float(item.get('price', 0))
        total_line = quantity * price
        subtotal += total_line
        
        # Concepto (puede ser largo, ajustar altura si es necesario)
        concept_encoded = concept.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(100, 7, concept_encoded[:50], 1, 0, 'L')
        pdf.cell(25, 7, f"{quantity:.2f}", 1, 0, 'R')
        pdf.cell(30, 7, f"{price:.2f} EUR", 1, 0, 'R')
        pdf.cell(35, 7, f"{total_line:.2f} EUR", 1, 1, 'R')
    
    # Si no hay items, mostrar mensaje
    if not items:
        pdf.cell(190, 7, "Sin items", 1, 1, 'C')
    
    # ===== PIE DEL DOCUMENTO =====
    y_bottom = 250
    pdf.set_y(y_bottom)
    
    # Cuadro de totales a la derecha
    pdf.set_font('Arial', '', 10)
    pdf.set_xy(120, y_bottom)
    
    # Calcular IVA y total
    iva_rate = 0.21
    iva_amount = subtotal * iva_rate
    total = subtotal + iva_amount
    
    # Subtotal
    pdf.cell(40, 7, "Subtotal:", 0, 0, 'L')
    pdf.cell(30, 7, f"{subtotal:.2f} EUR", 0, 1, 'R')
    
    # IVA
    pdf.set_x(120)
    pdf.cell(40, 7, f"IVA ({iva_rate*100:.0f}%):", 0, 0, 'L')
    pdf.cell(30, 7, f"{iva_amount:.2f} EUR", 0, 1, 'R')
    
    # Total
    pdf.set_x(120)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_line_width(0.5)
    pdf.line(120, pdf.get_y(), 200, pdf.get_y())
    pdf.set_y(pdf.get_y() + 2)
    pdf.set_x(120)
    pdf.cell(40, 8, "TOTAL A PAGAR:", 0, 0, 'L')
    pdf.cell(30, 8, f"{total:.2f} EUR", 0, 1, 'R')
    
    # Zona de firmas
    pdf.set_y(pdf.get_y() + 15)
    pdf.set_font('Arial', '', 10)
    col1, col2 = 30, 120
    pdf.set_xy(col1, pdf.get_y())
    pdf.cell(60, 5, "Firma Técnico", 0, 0, 'L')
    pdf.set_xy(col2, pdf.get_y())
    pdf.cell(60, 5, "Firma Cliente", 0, 1, 'L')
    
    # Líneas para firmas
    pdf.set_y(pdf.get_y() + 10)
    pdf.line(col1, pdf.get_y(), col1 + 60, pdf.get_y())
    pdf.line(col2, pdf.get_y(), col2 + 60, pdf.get_y())
    
    # Pie de página legal
    pdf.set_y(280)
    pdf.set_font('Arial', 'I', 7)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(190, 4, "Documento generado tecnológicamente. Este documento cumple con la normativa RGPD.", 0, 1, 'C')
    pdf.cell(190, 4, "Los datos personales contenidos en este documento están protegidos según la Ley Orgánica de Protección de Datos.", 0, 1, 'C')
    
    # Generar bytes del PDF
    pdf_bytes = pdf.output(dest='S')
    # Convertir a bytes si es bytearray
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    return pdf_bytes


def show_materials_page():
    """Muestra la vista de detalle de un parte de trabajo"""
    st.title("Detalle del Parte")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    try:
        # Obtener todos los partes de trabajo (no solo los abiertos)
        work_orders_response = supabase.table('work_orders').select(
            'id, created_at, client_id, technician_id, status, description_summary'
        ).eq('organization_id', org_id).order('created_at', desc=True).execute()
        
        if not work_orders_response.data:
            st.warning("No hay partes de trabajo. Crea un parte de trabajo primero.")
            return
        
        # Obtener nombres de clientes
        client_ids = [wo.get('client_id') for wo in work_orders_response.data if wo.get('client_id')]
        clients_dict = {}
        if client_ids:
            clients_response = supabase.table('clients').select('id, name').in_('id', list(set(client_ids))).execute()
            clients_dict = {client['id']: client['name'] for client in clients_response.data}
        
        # Obtener nombres de técnicos
        technician_ids = [wo.get('technician_id') for wo in work_orders_response.data if wo.get('technician_id')]
        technicians_dict = {}
        if technician_ids:
            technicians_response = supabase.table('profiles').select('id, full_name').in_('id', list(set(technician_ids))).execute()
            technicians_dict = {tech['id']: tech['full_name'] for tech in technicians_response.data}
        
        # Crear opciones para el selectbox
        work_order_options = {}
        work_order_data_dict = {}
        for wo in work_orders_response.data:
            wo_id = wo['id']
            created_at = wo.get('created_at', '')
            fecha = created_at[:10] if created_at and len(created_at) >= 10 else 'Sin fecha'
            client_id = wo.get('client_id')
            client_name = clients_dict.get(client_id, 'Sin cliente') if client_id else 'Sin cliente'
            status = wo.get('status', 'draft')
            
            label = f"{fecha} - {client_name} ({status})"
            work_order_options[label] = wo_id
            work_order_data_dict[wo_id] = wo
        
        if not work_order_options:
            st.warning("No hay partes de trabajo disponibles.")
            return
        
        # Selector de parte de trabajo
        selected_label = st.selectbox(
            "Selecciona un Parte de Trabajo",
            options=list(work_order_options.keys()),
            key="work_order_selector"
        )
        
        selected_work_order_id = work_order_options[selected_label]
        selected_work_order = work_order_data_dict[selected_work_order_id]
        
        st.divider()
        
        # Mostrar información del parte (cabecera)
        st.markdown("### Información del Parte")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            client_id = selected_work_order.get('client_id')
            client_name = clients_dict.get(client_id, 'Sin cliente') if client_id else 'Sin cliente'
            st.metric("Cliente", client_name)
            
            created_at = selected_work_order.get('created_at', '')
            fecha = created_at[:10] if created_at and len(created_at) >= 10 else 'Sin fecha'
            st.caption(f"Fecha: {fecha}")
        
        with col2:
            technician_id = selected_work_order.get('technician_id')
            technician_name = technicians_dict.get(technician_id, 'Sin asignar') if technician_id else 'Sin asignar'
            st.metric("Técnico", technician_name)
            
            status = selected_work_order.get('status', 'draft')
            status_display = {
                'draft': 'Borrador',
                'signed': 'Firmado',
                'closed': 'Cerrado'
            }
            st.caption(f"Estado: {status_display.get(status, status)}")
        
        with col3:
            st.metric("ID Parte", str(selected_work_order_id)[:8])
        
        # Descripción
        description = selected_work_order.get('description_summary', '')
        if description:
            st.markdown("**Descripción:**")
            st.write(description)
        
        st.divider()
        
        # Cargar items existentes del parte seleccionado
        items_response = supabase.table('work_order_items').select(
            'id, concept, quantity, price'
        ).eq('work_order_id', selected_work_order_id).order('created_at').execute()
        
        # Inicializar DataFrame
        if items_response.data:
            items_df = pd.DataFrame(items_response.data)
            # Asegurar que las columnas numéricas sean del tipo correcto
            items_df['quantity'] = pd.to_numeric(items_df['quantity'], errors='coerce').fillna(0)
            items_df['price'] = pd.to_numeric(items_df['price'], errors='coerce').fillna(0)
        else:
            # DataFrame vacío con las columnas necesarias
            items_df = pd.DataFrame(columns=['id', 'concept', 'quantity', 'price'])
            items_df['quantity'] = items_df['quantity'].astype(float)
            items_df['price'] = items_df['price'].astype(float)
        
        # Guardar datos originales en session_state para comparar cambios
        session_key = f"work_order_items_original_{selected_work_order_id}"
        if session_key not in st.session_state:
            st.session_state[session_key] = items_df.copy()
        
        original_df = st.session_state[session_key]
        
        # Preparar DataFrame para el editor (sin ID en la visualización, pero lo necesitamos para el diffing)
        editor_df = items_df.copy()
        
        # Añadir columna calculada "Total Línea"
        editor_df['Total Línea'] = editor_df['quantity'] * editor_df['price']
        
        # Reordenar columnas para el editor (ocultar ID pero mantenerlo para el diffing)
        display_df = editor_df[['concept', 'quantity', 'price', 'Total Línea']].copy()
        display_df.columns = ['Concepto', 'Unidades', 'Precio por Unidad', 'Precio Total']
        
        st.markdown("### Detalles de un Parte")
        st.caption("Añade, modifica o elimina líneas. Haz clic en 'Guardar Cambios' para aplicar las modificaciones.")
        
        # Editor de datos
        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Concepto": st.column_config.TextColumn(
                    "Concepto",
                    width="large",
                    required=True
                ),
                "Unidades": st.column_config.NumberColumn(
                    "Unidades",
                    width="small",
                    min_value=0,
                    step=0.01,
                    format="%.2f"
                ),
                "Precio por Unidad": st.column_config.NumberColumn(
                    "Precio por Unidad (€)",
                    width="medium",
                    min_value=0,
                    step=0.01,
                    format="%.2f"
                ),
                "Precio Total": st.column_config.NumberColumn(
                    "Precio Total (€)",
                    width="medium",
                    disabled=True,
                    format="%.2f"
                )
            },
            key=f"work_order_items_editor_{selected_work_order_id}"
        )
        
        # Recalcular Total después de edición
        if not edited_df.empty:
            # El edited_df tiene las columnas renombradas del data_editor
            if 'Unidades' in edited_df.columns and 'Precio por Unidad' in edited_df.columns:
                edited_df['Precio Total'] = edited_df['Unidades'] * edited_df['Precio por Unidad']
                total_parte = edited_df['Precio Total'].sum()
            else:
                # Fallback: usar las columnas originales si no están renombradas
                total_parte = (edited_df['quantity'] * edited_df['price']).sum() if 'quantity' in edited_df.columns else 0
        else:
            total_parte = 0
        
        st.divider()
        
        col_total1, col_total2, col_total3 = st.columns([1, 2, 1])
        with col_total2:
            st.metric("Total del Parte", f"{total_parte:.2f} €")
            
            # Botón para descargar PDF
            try:
                pdf_bytes = create_work_order_pdf(selected_work_order_id, supabase, org_id)
                st.download_button(
                    label="Descargar Parte en PDF",
                    data=pdf_bytes,
                    file_name=f"parte_{str(selected_work_order_id)[:8]}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="secondary"
                )
            except Exception as e:
                st.error(f"Error al generar PDF: {str(e)}")
        
        st.divider()
        
        # Botón para guardar cambios
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            save_button = st.button("Guardar Cambios", use_container_width=True, type="primary")
        
        # Lógica de diffing y guardado
        if save_button:
            # Estrategia de diffing: mapear por posición (índice) ya que st.data_editor mantiene el orden
            inserts = []
            updates = []
            deletes = []
            
            # Crear listas de filas originales y editadas
            original_rows = []
            if not original_df.empty:
                for idx, row in original_df.iterrows():
                    original_rows.append({
                        'id': row.get('id'),
                        'concept': str(row.get('concept', '')),
                        'quantity': float(row.get('quantity', 0)),
                        'price': float(row.get('price', 0))
                    })
            
            edited_rows = []
            for idx, row in edited_df.iterrows():
                # El edited_df tiene columnas renombradas, usar los nombres correctos
                concept = row.get('Concepto', row.get('concept', ''))
                quantity = row.get('Unidades', row.get('quantity', 0))
                price = row.get('Precio por Unidad', row.get('price', 0))
                
                edited_rows.append({
                    'concept': str(concept),
                    'quantity': float(pd.to_numeric(quantity, errors='coerce') or 0),
                    'price': float(pd.to_numeric(price, errors='coerce') or 0)
                })
            
            # Comparar por posición (índice)
            max_len = max(len(original_rows), len(edited_rows))
            
            for i in range(max_len):
                if i < len(original_rows) and i < len(edited_rows):
                    # Fila existe en ambos - puede ser modificación
                    orig_row = original_rows[i]
                    edit_row = edited_rows[i]
                    
                    # Verificar si hubo cambios
                    if (orig_row['concept'] != edit_row['concept'] or
                        abs(orig_row['quantity'] - edit_row['quantity']) > 0.01 or
                        abs(orig_row['price'] - edit_row['price']) > 0.01):
                        # Hay cambios - actualizar
                        if orig_row['id']:
                            updates.append({
                                'id': orig_row['id'],
                                'concept': edit_row['concept'],
                                'quantity': edit_row['quantity'],
                                'price': edit_row['price']
                            })
                elif i < len(original_rows) and i >= len(edited_rows):
                    # Fila eliminada
                    if original_rows[i]['id']:
                        deletes.append(original_rows[i]['id'])
                elif i >= len(original_rows) and i < len(edited_rows):
                    # Nueva fila
                    inserts.append({
                        'concept': edited_rows[i]['concept'],
                        'quantity': edited_rows[i]['quantity'],
                        'price': edited_rows[i]['price'],
                        'work_order_id': selected_work_order_id
                    })
            
            # Ejecutar operaciones
            success_count = 0
            error_messages = []
            
            # Insertar nuevas filas
            if inserts:
                try:
                    insert_response = supabase.table('work_order_items').insert(inserts).execute()
                    if insert_response.data:
                        success_count += len(inserts)
                except Exception as e:
                    error_messages.append(f"Error al insertar: {str(e)}")
            
            # Actualizar filas modificadas
            for update in updates:
                try:
                    update_response = supabase.table('work_order_items').update({
                        'concept': update['concept'],
                        'quantity': update['quantity'],
                        'price': update['price']
                    }).eq('id', update['id']).execute()
                    if update_response.data:
                        success_count += 1
                except Exception as e:
                    error_messages.append(f"Error al actualizar ID {update['id']}: {str(e)}")
            
            # Eliminar filas
            if deletes:
                try:
                    for delete_id in deletes:
                        delete_response = supabase.table('work_order_items').delete().eq('id', delete_id).execute()
                        if delete_response.data or delete_response.data == []:
                            success_count += 1
                except Exception as e:
                    error_messages.append(f"Error al eliminar: {str(e)}")
            
            # Mostrar feedback
            if inserts or updates or deletes:
                feedback_parts = []
                if inserts:
                    feedback_parts.append(f"{len(inserts)} nueva(s)")
                if updates:
                    feedback_parts.append(f"{len(updates)} actualizada(s)")
                if deletes:
                    feedback_parts.append(f"{len(deletes)} eliminada(s)")
                
                if success_count > 0:
                    st.success(f"{success_count} línea(s) procesada(s) correctamente ({', '.join(feedback_parts)})")
                else:
                    st.warning("No se pudo procesar ninguna operación")
                
                if error_messages:
                    for error_msg in error_messages:
                        st.error(error_msg)
                
                # Limpiar session_state y recargar
                if session_key in st.session_state:
                    del st.session_state[session_key]
                st.rerun()
            else:
                st.info("No hay cambios para guardar")
        
    except Exception as e:
        st.error(f"Error al cargar gestión de materiales: {str(e)}")
        st.exception(e)


def show_company_page():
    """Muestra la página de configuración de la empresa"""
    st.title("Mi Empresa")
    
    supabase = get_authenticated_client()
    if not supabase or not st.session_state.organization_id:
        st.error("No se pudo conectar a la base de datos")
        return
    
    org_id = st.session_state.organization_id
    
    try:
        # Verificar rol del usuario (asumimos que 'admin' o 'manager' pueden editar)
        user_id = st.session_state.user.id if st.session_state.user else None
        user_profile = None
        if user_id:
            profile_response = supabase.table('profiles').select('role').eq('id', user_id).execute()
            if profile_response.data:
                user_profile = profile_response.data[0]
                user_role = user_profile.get('role', '')
        
        # Obtener datos de la organización
        # Seleccionar solo las columnas que sabemos que existen
        org_response = supabase.table('organizations').select('name, address, cif').eq('id', org_id).execute()
        
        if not org_response.data:
            st.error("No se encontró la organización")
            return
        
        org_data = org_response.data[0]
        org_name = org_data.get('name', 'Sin nombre')
        org_address = org_data.get('address', '')
        org_cif = org_data.get('cif', '')
        
        # Intentar obtener logo_url por separado (si la columna existe)
        logo_url = None
        try:
            logo_response = supabase.table('organizations').select('logo_url').eq('id', org_id).execute()
            if logo_response.data and 'logo_url' in logo_response.data[0]:
                logo_url = logo_response.data[0].get('logo_url')
        except:
            # Si la columna no existe, logo_url será None
            logo_url = None
        
        # Mostrar datos actuales de la empresa
        st.markdown("### Información de la Empresa")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Nombre", org_name)
            if org_address:
                st.caption(f"Dirección: {org_address}")
        
        with col2:
            if org_cif:
                st.metric("CIF", org_cif)
        
        st.divider()
        
        # Sección de Logo
        st.markdown("### Logo de la Empresa")
        
        # Mostrar logo actual si existe
        if logo_url:
            try:
                st.image(logo_url, width=200, caption="Logo actual")
            except Exception as e:
                st.warning(f"No se pudo cargar el logo: {str(e)}")
        else:
            st.info("No hay logo configurado")
        
        # Widget de subida de logo
        uploaded_file = st.file_uploader(
            "Seleccionar nuevo logo",
            type=['png', 'jpg', 'jpeg'],
            help="Formatos permitidos: PNG, JPG, JPEG. Tamaño máximo: 2MB"
        )
        
        if uploaded_file is not None:
            # Validar tamaño del archivo (2MB máximo)
            file_size = len(uploaded_file.getvalue())
            max_size = 2 * 1024 * 1024  # 2MB en bytes
            
            if file_size > max_size:
                st.error(f"El archivo es demasiado grande. Tamaño máximo: 2MB. Tu archivo: {file_size / 1024 / 1024:.2f}MB")
            else:
                # Mostrar preview de la imagen
                st.image(uploaded_file, width=200, caption="Vista previa del nuevo logo")
                
                # Botón para actualizar logo
                if st.button("Actualizar Logo", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Subiendo logo..."):
                            # Generar nombre de archivo único
                            timestamp = int(datetime.now().timestamp())
                            file_extension = uploaded_file.name.split('.')[-1].lower()
                            file_name = f"logo_{org_id}_{timestamp}.{file_extension}"
                            
                            # Leer el contenido del archivo
                            file_content = uploaded_file.getvalue()
                            
                            # Subir archivo a Supabase Storage
                            # Primero eliminar logo anterior si existe (opcional, para limpiar)
                            # No es crítico, pero ayuda a mantener el storage limpio
                            
                            storage_response = supabase.storage.from_('company-logos').upload(
                                file_name,
                                file_content,
                                file_options={"content-type": uploaded_file.type, "upsert": "true"}
                            )
                            
                            # Verificar que la subida fue exitosa
                            if storage_response:
                                # Obtener URL pública del archivo
                                # El método get_public_url devuelve un diccionario con la URL
                                try:
                                    public_url_data = supabase.storage.from_('company-logos').get_public_url(file_name)
                                    
                                    # Manejar diferentes formatos de respuesta
                                    if isinstance(public_url_data, dict):
                                        public_url = public_url_data.get('publicUrl') or public_url_data.get('public_url') or public_url_data.get('url', '')
                                    elif isinstance(public_url_data, str):
                                        public_url = public_url_data
                                    else:
                                        # Construir URL manualmente
                                        supabase_url = st.secrets["supabase"]["url"]
                                        public_url = f"{supabase_url}/storage/v1/object/public/company-logos/{file_name}"
                                    
                                    if not public_url:
                                        raise ValueError("No se pudo obtener la URL pública")
                                    
                                except Exception as url_error:
                                    # Fallback: construir URL manualmente
                                    supabase_url = st.secrets["supabase"]["url"]
                                    public_url = f"{supabase_url}/storage/v1/object/public/company-logos/{file_name}"
                                
                                # Actualizar la tabla organizations
                                # Intentar actualizar logo_url, pero manejar si la columna no existe
                                try:
                                    update_response = supabase.table('organizations').update({
                                        'logo_url': public_url
                                    }).eq('id', org_id).execute()
                                    
                                    if update_response.data:
                                        st.success("Logo actualizado correctamente")
                                        st.toast("Logo actualizado correctamente", icon="✅")
                                        st.rerun()
                                    else:
                                        st.error("Error al actualizar la base de datos")
                                except Exception as update_error:
                                    error_msg = str(update_error)
                                    if 'logo_url' in error_msg.lower() or 'column' in error_msg.lower():
                                        st.error("La columna 'logo_url' no existe en la tabla 'organizations'. Por favor, añádela primero a la base de datos.")
                                        st.info("Para añadir la columna, ejecuta en Supabase SQL Editor: ALTER TABLE organizations ADD COLUMN logo_url TEXT;")
                                    else:
                                        st.error(f"Error al actualizar la base de datos: {error_msg}")
                            else:
                                st.error("Error al subir el archivo a Storage")
                    except Exception as upload_error:
                        st.error(f"Error al procesar el logo: {str(upload_error)}")
                        # Log del error para debugging
                        if hasattr(upload_error, 'message'):
                            st.caption(f"Detalle: {upload_error.message}")
                    
                    except Exception as e:
                        st.error(f"Error al procesar el logo: {str(e)}")
                        st.exception(e)
        
        st.divider()
        
        # Información adicional
        st.markdown("### Información")
        st.caption("El logo se utilizará en los documentos PDF generados (partes de trabajo, facturas, etc.)")
        st.caption("Tamaño recomendado: 200x200px o similar. Formatos: PNG, JPG, JPEG")
        
    except Exception as e:
        st.error(f"Error al cargar datos de la empresa: {str(e)}")
        st.exception(e)


# Aplicación principal
def main():
    if not st.session_state.authenticated:
        show_login_page()
    else:
        page = show_sidebar()
        
        if page == "Dashboard":
            show_dashboard()
        elif page == "Crear Parte":
            show_create_work_order_page()
        elif page == "Partes de Trabajo":
            show_work_orders_page()
        elif page == "Detalles de un Parte":
            show_materials_page()
        elif page == "Mi Empresa":
            show_company_page()
        elif page == "Business Intelligence":
            show_bi_page()


if __name__ == "__main__":
    main()

