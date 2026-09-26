variable "tenancy_ocid" { type = string }
variable "user_ocid" { type = string }
variable "fingerprint" { type = string }
variable "private_key_path" { type = string }
variable "region" { type = string }
variable "compartment_ocid" { type = string }
variable "ssh_public_key" { type = string }
variable "ssh_allowed_cidr" {
  type        = string
  description = "Seu IP público em CIDR, por exemplo 203.0.113.10/32."
}
variable "availability_domain" {
  type        = string
  default     = ""
  description = "Opcional. Vazio usa o primeiro domínio disponível."
}

