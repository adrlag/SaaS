# Field Service Management - Panel de Administración

Aplicación SaaS B2B para gestión de partes de trabajo construida con Streamlit y Supabase.

## Características

- 🔐 Autenticación segura con Supabase Auth
- 📊 Dashboard con métricas clave
- 👥 Gestión de clientes
- 📋 Gestión de partes de trabajo con filtros
- 🔒 Row Level Security (RLS) habilitado - todas las queries usan el token de sesión del usuario

## Requisitos Previos

- Python 3.8 o superior
- Cuenta de Supabase con proyecto configurado
- Base de datos con las siguientes tablas:
  - `profiles` (id, full_name, role, organization_id)
  - `clients` (id, name, address, phone, organization_id)
  - `work_orders` (id, client_id, technician_id, status, description_summary, organization_id)

## Instalación

1. Clona o descarga este repositorio

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Configura los secrets de Streamlit:
   - Crea el directorio `.streamlit` si no existe:
   ```bash
   mkdir -p .streamlit
   ```
   
   - Crea el archivo `.streamlit/secrets.toml` con tu configuración de Supabase:
   ```toml
   [supabase]
   url = "https://tu-proyecto.supabase.co"
   anon_key = "tu-anon-key-aqui"
   ```
   
   **Importante**: El archivo `secrets.toml` está en `.gitignore` por defecto. No lo subas a tu repositorio.

## Configuración de Supabase

### Row Level Security (RLS)

Es **CRÍTICO** que tengas RLS habilitado en todas las tablas y que las políticas permitan acceso basado en `organization_id`. Ejemplo de políticas:

```sql
-- Política para profiles
CREATE POLICY "Users can view own profile"
ON profiles FOR SELECT
USING (auth.uid() = id);

-- Política para clients
CREATE POLICY "Users can manage clients in their organization"
ON clients FOR ALL
USING (organization_id IN (
  SELECT organization_id FROM profiles WHERE id = auth.uid()
));

-- Política para work_orders
CREATE POLICY "Users can manage work orders in their organization"
ON work_orders FOR ALL
USING (organization_id IN (
  SELECT organization_id FROM profiles WHERE id = auth.uid()
));
```

## Uso

1. Ejecuta la aplicación:
```bash
streamlit run app.py
```

2. Abre tu navegador en la URL que Streamlit te indique (normalmente `http://localhost:8501`)

3. Inicia sesión con tus credenciales de Supabase

4. Navega por las diferentes secciones:
   - **Dashboard**: Visualiza métricas clave
   - **Clientes**: Gestiona tu lista de clientes
   - **Partes de Trabajo**: Visualiza y filtra partes de trabajo

## Estructura del Proyecto

```
SaaS/
├── app.py                    # Aplicación principal
├── requirements.txt          # Dependencias Python
├── README.md                 # Este archivo
└── .streamlit/
    ├── secrets.toml          # Configuración de Supabase (no incluido en git)
    └── config.toml.example   # Ejemplo de configuración
```

## Seguridad

- ✅ Todas las queries a Supabase usan el token de sesión del usuario autenticado
- ✅ RLS garantiza que los usuarios solo accedan a datos de su organización
- ✅ Las credenciales se almacenan en `st.secrets` (no en el código)
- ✅ El `organization_id` se obtiene automáticamente del perfil del usuario

## Notas Importantes

- **NUNCA** uses la Service Key de Supabase en esta aplicación
- El `organization_id` se obtiene automáticamente del perfil del usuario después del login
- Todas las operaciones de base de datos respetan el RLS configurado en Supabase

## Solución de Problemas

### Error: "No se pudo conectar a la base de datos"
- Verifica que `secrets.toml` esté correctamente configurado
- Asegúrate de que la URL y la anon_key sean correctas

### Error: "No se encontró el perfil del usuario"
- Verifica que el usuario tenga un registro en la tabla `profiles`
- Asegúrate de que el `organization_id` esté configurado en el perfil

### Error de permisos en queries
- Verifica que RLS esté habilitado y las políticas estén correctamente configuradas
- Asegúrate de que las políticas permitan acceso basado en `organization_id`

## Licencia

Este proyecto es privado y confidencial.

