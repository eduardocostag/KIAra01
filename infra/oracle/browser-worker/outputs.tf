output "public_ip" {
  value = oci_core_instance.worker.public_ip
}

output "worker_host" {
  value = "${replace(oci_core_instance.worker.public_ip, ".", "-")}.sslip.io"
}

output "worker_url" {
  value = "https://${replace(oci_core_instance.worker.public_ip, ".", "-")}.sslip.io"
}

