import os
import subprocess as sp
import json
from dotenv import load_dotenv

load_dotenv()


parameters = {
    "resource_group": os.getenv("RESOURCE_GROUP"),
    "location": os.getenv("LOCATION", "eastus"),
    "acr_name": os.getenv("ACR_NAME"),
    "image_name": os.getenv("IMAGE_NAME"),
    "tag_name": os.getenv("TAG_NAME"),
    "service_principal_name": os.getenv("SERVICE_PRINCIPAL_NAME"),
    "container_name": os.getenv("CONTAINER_NAME", "um-app-container"),
    "dns_name_label": os.getenv("DNS_NAME_LABEL", f"um-app-{os.getpid()}"), #QUE SEA ALEATORIO - 0-999
    "cpu": os.getenv("CPU", "1.0"),
    "memory_gb": os.getenv("MEMORY_GB", "1.5"),
    "port": os.getenv("PORT", "80")
}


def run_command(command, capture_output=False, text=False, input_data=None):
    print(f"Ejecutando: {' '.join(command)}")
    try:
        result = sp.run(command, input=input_data, capture_output=capture_output, text=text, check=True)
        return result
    except sp.CalledProcessError as e:
        print(f"Error ejecutando el comando: {e}")
        if e.stdout: print(f"Stdout: {e.stdout}")
        if e.stderr: print(f"Stderr: {e.stderr}")
        exit(1)

def check_or_create_resource_group(params):
    print(f"\n--- Verificando Grupo de Recursos: {params['resource_group']} ---")
    result = run_command(['az', 'group', 'exists', '--name', params['resource_group']], capture_output=True, text=True)
    if 'false' in result.stdout:
        print("Creando grupo de recursos...")
        run_command(['az', 'group', 'create', '--name', params['resource_group'], '--location', params['location']])
    else:
        print("El grupo de recursos ya existe.")

def check_or_create_acr(params):
    print(f"\n--- Verificando ACR: {params['acr_name']} ---")
    try:
        sp.run(['az', 'acr', 'show', '--name', params['acr_name'], '--resource-group', params['resource_group']], capture_output=False, check=True)
        print("El ACR ya existe.")
    except sp.CalledProcessError:
        print("Creando ACR...")
        run_command(['az', 'acr', 'create', '--name', params['acr_name'], '--resource-group', params['resource_group'], '--sku', 'Standard'])

def docker_build(params):
    print(f"\n--- Construyendo imagen Docker ---")
    run_command(['docker', 'build', '-t', f"{params['image_name']}:{params['tag_name']}", '.'])

def docker_tag(params):
    print(f"\n--- Etiquetando imagen para ACR ---")
    acr_login_server = run_command(['az', 'acr', 'show', '--name', params['acr_name'], '--query', 'loginServer', '--output', 'tsv'], capture_output=True, text=True).stdout.strip()
    full_tag = f"{acr_login_server}/{params['image_name']}:{params['tag_name']}"
    run_command(['docker', 'tag', f"{params['image_name']}:{params['tag_name']}", full_tag])
    return acr_login_server, full_tag

def docker_push(full_image_tag):
    print(f"\n--- Subiendo imagen a ACR ---")
    run_command(['docker', 'push', full_image_tag])

def get_acr_id(params):
    result = run_command(['az', 'acr', 'show', '--name', params['acr_name'], '--resource-group', params['resource_group'], '--query', 'id', '--output', 'tsv'], capture_output=True, text=True)
    return result.stdout.strip()

def get_service_principal_id(params):
    """Obtiene el appId del Service Principal por nombre."""
    sp_list = run_command([
        'az', 'ad', 'sp', 'list',
        '--display-name', params['service_principal_name'],
        '--query', '"[].appId"', '--output', 'tsv'
    ], capture_output=True, text=True)
    return sp_list.stdout.strip()

def create_service_principal(params):
    """Crea un Service Principal con permisos 'acrpull' y retorna sus credenciales."""
    acr_scope_id = get_acr_id(params)
    sp_creds_result = run_command([
        'az', 'ad', 'sp', 'create-for-rbac',
        '--name', params['service_principal_name'],
        '--scopes', acr_scope_id,
        '--role', 'acrpull',
        '--query', 'password'
    ], capture_output=True, text=True)
    credentials = json.loads(sp_creds_result.stdout)
    return credentials['appId'], credentials['password']

def reset_service_principal_password(app_id):
    """Resetea la credencial del Service Principal y retorna el nuevo password."""
    password = run_command([
        'az', 'ad', 'sp', 'credential', 'reset',
        '--id', app_id,
        '--query', '[0].password', '--output', 'tsv'
    ], capture_output=True, text=True).stdout.strip()
    return password

def create_or_get_service_principal(params):
    print(f"\n--- Asegurando Service Principal ---")
    app_id = get_service_principal_id(params)
    if not app_id:
        print("Creando Service Principal con permisos 'acrpull'...")
        app_id, password = create_service_principal(params)
    else:
        print("Reseteando credencial del Service Principal...")
        password = reset_service_principal_password(app_id)
    return app_id, password

def deploy_container_instance(params, login_server, image_tag, sp_app_id, sp_password):
    """Despliega la imagen del contenedor en Azure Container Instances."""
    print(f"\n--- Desplegando contenedor en Azure ---")
    deploy_cmd = [
        'az', 'container', 'create',
        '--resource-group', params['resource_group'],
        '--name', params['container_name'],
        '--image', image_tag,
        '--cpu', params['cpu'],
        '--memory', params['memory_gb'],
        '--registry-login-server', login_server,
        '--registry-username', sp_app_id,
        '--registry-password', sp_password,
        '--ip-address', 'Public',
        '--dns-name-label', params['dns_name_label'],
        '--ports', params['port']
    ]
    run_command(deploy_cmd)
    print("Contenedor desplegado exitosamente.")


def main():
    """Flujo principal del script de despliegue."""
    check_or_create_resource_group(parameters)
    check_or_create_acr(parameters)

    #docker_build(parameters)
    acr_login_server, full_image_tag = docker_tag(parameters)

    sp_app_id, sp_password = create_or_get_service_principal(parameters)
    
    docker_push(full_image_tag)


    deploy_container_instance(parameters, acr_login_server, full_image_tag, sp_app_id, sp_password)

    print("\n--- Obteniendo URL final ---")
    fqdn_result = run_command(['az', 'container', 'show', '--resource-group', parameters['resource_group'], '--name', parameters['container_name'], '--query', 'ipAddress.fqdn', '--output', 'tsv'], capture_output=True, text=True)
    
    print("\n\n✅ ¡DESPLIEGUE COMPLETADO!")
    print(f"Tu aplicación está publicada y accesible en la siguiente URL:")
    print(f"http://{fqdn_result.stdout.strip()}:{parameters['port']}")


if __name__ == "__main__":
    main()