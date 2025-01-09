import sys
import yaml

# Map each service to its Docker image repository (without tag).
SERVICES_TO_UPDATE = {
    "lectio_api": "robounord/lectio_msg_playwright_api",
    "lectio_worker": "robounord/lectio_msg_playwright_worker"
}

def update_docker_compose(version: str) -> int:
    with open("docker-compose.yml", 'r') as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    if 'services' not in data:
        print("Key 'services' not found in docker-compose.yml.")
        return 1

    # For each service, update the image to <repo>:<new_version>
    for service_name, docker_image_repo in SERVICES_TO_UPDATE.items():
        if service_name in data['services']:
            old_image = data['services'][service_name].get('image', 'unknown')
            new_image = f"{docker_image_repo}:{version}"
            print(f"Updating {service_name} image from '{old_image}' to '{new_image}'")
            data['services'][service_name]['image'] = new_image
        else:
            print(f"Service '{service_name}' not found in docker-compose.yml. Skipped.")

    # Write the updated content back to docker-compose.yml
    with open("docker-compose.yml", 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return 0  # success

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python update_docker_compose.py <new_version>")
        sys.exit(1)

    new_version_arg = sys.argv[1]
    sys.exit(update_docker_compose(new_version_arg))
