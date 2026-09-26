data "oci_identity_availability_domains" "available" {
  compartment_id = var.tenancy_ocid
}

locals {
  availability_domain = var.availability_domain != "" ? var.availability_domain : data.oci_identity_availability_domains.available.availability_domains[0].name
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_vcn" "kiara" {
  compartment_id = var.compartment_ocid
  cidr_blocks     = ["10.42.0.0/16"]
  display_name    = "kiara-browser-vcn"
  dns_label       = "kiarabrowser"
}

resource "oci_core_internet_gateway" "kiara" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.kiara.id
  enabled        = true
  display_name   = "kiara-browser-internet"
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.kiara.id
  display_name   = "kiara-browser-public-routes"
  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.kiara.id
  }
}

resource "oci_core_security_list" "worker" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.kiara.id
  display_name   = "kiara-browser-security"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6"
    source   = var.ssh_allowed_cidr
    tcp_options { min = 22, max = 22 }
  }
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options { min = 80, max = 80 }
  }
  ingress_security_rules {
    protocol = "6"
    source   = "0.0.0.0/0"
    tcp_options { min = 443, max = 443 }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.kiara.id
  cidr_block                 = "10.42.1.0/24"
  display_name               = "kiara-browser-public"
  dns_label                  = "worker"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.worker.id]
  prohibit_public_ip_on_vnic = false
}

resource "oci_core_instance" "worker" {
  availability_domain = local.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "kiara-browser-worker"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    display_name     = "kiara-browser-worker"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = 50
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(<<-CLOUD_INIT
      #cloud-config
      package_update: true
      packages:
        - docker.io
        - docker-compose-v2
        - ca-certificates
      runcmd:
        - systemctl enable --now docker
        - usermod -aG docker ubuntu
        - mkdir -p /opt/kiara-browser
        - chown -R ubuntu:ubuntu /opt/kiara-browser
        - ufw allow 22/tcp
        - ufw allow 80/tcp
        - ufw allow 443/tcp
        - ufw --force enable
      CLOUD_INIT
    )
  }
}

