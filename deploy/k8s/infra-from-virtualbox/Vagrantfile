require 'yaml'

# Load configuration from the YAML file
vm_config = YAML.load_file('cluster_config.yaml')

Vagrant.configure("2") do |config|
  config.vbguest.auto_update = false

  # Iterate over each VM defined in the YAML file
  vm_config['vms'].each do |vm|
    config.vm.define vm['name'] do |node|
      node.vm.box = vm['box'] # Use a box specified in the YAML file
      node.vm.hostname = vm['name']
      node.vm.provider "virtualbox" do |vb|
        vb.memory = vm['memory']
        vb.cpus = vm['cpus']
      end

      # Add disk if specified in the YAML file
      if vm['disk']
        disk_name = "#{vm['name']}_disk"
        node.vm.disk :disk, size: "100GB", name: disk_name
      end

      # Run script to load rbd module
      node.vm.provision "shell", inline: <<-SHELL
        echo "Loading rbd module..."
        sudo modprobe rbd
        echo rbd | sudo tee -a /etc/modules
      SHELL
    end
  end

  # Disable shared folder
  config.vm.synced_folder ".", "/vagrant", disabled: true

  # Define a private network for all VMs
  config.vm.network "private_network", type: "dhcp"
end
