-- Replace or extend these values with the ownership table supplied by the organizers.
INSERT INTO component_ownership (dataset, component, team) VALUES
  ('bgl', 'KERNEL', 'Compute Reliability'),
  ('openstack', 'nova-api', 'API Platform'),
  ('openstack', 'nova-compute', 'Compute Platform'),
  ('openstack', 'nova-scheduler', 'Scheduling Platform')
ON CONFLICT (dataset, component) DO UPDATE SET team = EXCLUDED.team;

