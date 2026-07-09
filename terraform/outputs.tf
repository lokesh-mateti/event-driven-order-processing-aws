output "opensearch_endpoint" {
  value = aws_opensearch_domain.orders.endpoint
}

output "elasticache_endpoint" {
  value = aws_elasticache_cluster.orders.cache_nodes[0].address
}