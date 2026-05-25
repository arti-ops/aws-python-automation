// =============================================
// LOGOUT
// =============================================

async function logout() {
    await fetch('/logout');
    window.location.href = '/';
}

// =============================================
// REFRESH INSTANCES
// =============================================

async function refreshInstances() {
    const container = document.querySelector('.instance-container');
    container.innerHTML = '<p>Loading...</p>';

    try {
        const res = await fetch('/instances');
        const data = await res.json();
        const instances = data.instances;

        // Update dashboard cards
        const running = instances.filter(i => i.state === 'running').length;
        const stopped = instances.filter(i => i.state === 'stopped').length;
        const cards = document.querySelectorAll('.dashboard-cards .card h2');
        if (cards.length >= 3) {
            cards[0].textContent = instances.length;
            cards[1].textContent = running;
            cards[2].textContent = stopped;
        }

        if (instances.length === 0) {
            container.innerHTML = '<p>No instances found.</p>';
            return;
        }

        container.innerHTML = '';

        instances.forEach(instance => {
            const badgeClass = instance.state === 'running' ? 'running-badge' : 'stopped-badge';
            const card = document.createElement('div');
            card.className = 'instance-card';
            card.innerHTML = `
                <div class="instance-top">
                    <h3>${instance.instance_name}</h3>
                    <span class="${badgeClass}">${instance.state}</span>
                </div>
                <div class="instance-details">
                    <p><i class="fa-solid fa-id-card"></i> Instance ID: ${instance.instance_id}</p>
                    <p><i class="fa-solid fa-microchip"></i> Type: ${instance.type}</p>
                    <p><i class="fa-solid fa-network-wired"></i> Public IP: ${instance.public_ip}</p>
                    <p><i class="fa-solid fa-lock"></i> Private IP: ${instance.private_ip}</p>
                </div>
                <div class="instance-buttons">
                    <button class="start-btn">Start</button>
                    <button class="stop-btn">Stop</button>
                    <button class="terminate-btn">Terminate</button>
                </div>
            `;

            // ✅ THE FIX - attach clicks properly, no quote conflicts
            card.querySelector('.start-btn').addEventListener('click', () => startInstance(instance.instance_id));
            card.querySelector('.stop-btn').addEventListener('click', () => stopInstance(instance.instance_id));
            card.querySelector('.terminate-btn').addEventListener('click', () => terminateInstance(instance.instance_id));

            container.appendChild(card);
        });

    } catch (err) {
        container.innerHTML = `<p style="color:red">Error: ${err.message}</p>`;
        console.error(err);
    }
}

// =============================================
// START INSTANCE
// =============================================

async function startInstance(instanceId) {
    if (!confirm('Start this instance?')) return;
    try {
        const res = await fetch(`/start/${instanceId}`, { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Instance started!');
        refreshInstances();
    } catch (err) {
        alert('Error starting instance');
    }
}

// =============================================
// STOP INSTANCE
// =============================================

async function stopInstance(instanceId) {
    if (!confirm('Stop this instance?')) return;
    try {
        const res = await fetch(`/stop/${instanceId}`, { method: 'POST' });
        const data = await res.json();
        alert(data.message || 'Instance stopped!');
        refreshInstances();
    } catch (err) {
        alert('Error stopping instance');
    }
}

// =============================================
// TERMINATE INSTANCE
// =============================================

async function terminateInstance(instanceId) {
    if (!confirm('TERMINATE this instance? This cannot be undone!')) return;
    try {
        const res = await fetch(`/delete/${instanceId}`, { method: 'DELETE' });
        const data = await res.json();
        alert(data.message || 'Instance terminated!');
        refreshInstances();
    } catch (err) {
        alert('Error terminating instance');
    }
}

// =============================================
// LOAD KEYPAIRS
// =============================================

async function loadKeypairs() {
    try {
        const res = await fetch('/keypairs');
        const data = await res.json();
        const select = document.getElementById('keypair-name');
        select.innerHTML = '';
        data.keypairs.forEach(k => {
            const opt = document.createElement('option');
            opt.value = k.key_name;
            opt.textContent = k.key_name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('Error loading keypairs', err);
    }
}

// =============================================
// LOAD SECURITY GROUPS
// =============================================

async function loadSecurityGroups() {
    try {
        const res = await fetch('/security-groups');
        const data = await res.json();
        const select = document.getElementById('security-group-name');
        select.innerHTML = '';
        data.security_groups.forEach(sg => {
            const opt = document.createElement('option');
            opt.value = sg.group_name;
            opt.textContent = sg.group_name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('Error loading security groups', err);
    }
}

// =============================================
// KEYPAIR OPTION TOGGLE
// =============================================

document.getElementById('keypair-option').addEventListener('change', function () {
    const existing = document.getElementById('existing-keypair-group');
    const newGroup = document.getElementById('new-keypair-group');
    if (this.value === 'Use Existing') {
        existing.style.display = 'block';
        newGroup.style.display = 'none';
    } else {
        existing.style.display = 'none';
        newGroup.style.display = 'block';
    }
});

// =============================================
// SECURITY GROUP OPTION TOGGLE
// =============================================

document.getElementById('security-group-option').addEventListener('change', function () {
    const existing = document.getElementById('existing-security-group');
    const newGroup = document.getElementById('new-security-group');
    if (this.value === 'Use Existing') {
        existing.style.display = 'block';
        newGroup.style.display = 'none';
    } else {
        existing.style.display = 'none';
        newGroup.style.display = 'block';
    }
});

// =============================================
// CREATE INSTANCE
// =============================================

const osType = document.getElementById('os-type').value.toLowerCase().replace(/\s+/g, '-');    const instanceType = document.getElementById('instance-type').value;
    const keypairOption = document.getElementById('keypair-option').value;
    const securityGroupOption = document.getElementById('security-group-option').value;
    const volumeSize = document.getElementById('volume-size').value || 8;

    const keypairMode = keypairOption === 'Use Existing' ? 'existing' : 'create_new';
    const sgMode = securityGroupOption === 'Use Existing' ? 'existing' : 'create_new';
    const keyName = keypairMode === 'existing' ? document.getElementById('keypair-name').value : null;
    const sgName = sgMode === 'existing' ? document.getElementById('security-group-name').value : null;

    if (!instanceName) {
        alert('Please enter an Instance Name!');
        return;
    }

    const body = {
        os_type: osType === 'amazon-linux' ? 'amazon-linux' : 'ubuntu',
        instance_type: instanceType,
        keypair_mode: keypairMode,
        key_name: keyName,
        security_group_mode: sgMode,
        security_group_name: sgName,
        instance_name: instanceName,
        volume_size: parseInt(volumeSize)
    };

    this.textContent = 'Launching...';
    this.disabled = true;

    try {
        const res = await fetch('/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (res.ok) {
            alert(`Instance Created!\nID: ${data.instance_id}\nName: ${data.instance_name}`);
            refreshInstances();
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error creating instance');
        console.error(err);
    }

    this.textContent = 'Launch Instance';
    this.disabled = false;
});

// =============================================
// CREATE EBS
// =============================================

async function createEBS() {
    const instanceName = document.getElementById('ebs-instance-name').value;
    const size = document.getElementById('ebs-size').value;
    const volumeType = document.getElementById('ebs-type').value;
    const tagName = document.getElementById('ebs-tag').value || 'MyEBSVolume';

    if (!instanceName || !size) {
        alert('Please enter Instance Name and Size!');
        return;
    }

    try {
        const res = await fetch('/storage/ebs/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                instance_name: instanceName,
                size: parseInt(size),
                volume_type: volumeType,
                tag_name: tagName
            })
        });
        const data = await res.json();
        if (res.ok) {
            alert(`EBS Created!\nVolume ID: ${data.volume_id}`);
            loadEBSVolumes();
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error creating EBS');
    }
}

// =============================================
// LOAD EBS VOLUMES
// =============================================

async function loadEBSVolumes() {
    const container = document.getElementById('ebs-container');
    container.innerHTML = '<p>Loading...</p>';

    try {
        const res = await fetch('/storage/ebs');
        const data = await res.json();

        if (data.volumes.length === 0) {
            container.innerHTML = '<p>No EBS volumes found.</p>';
            return;
        }

        container.innerHTML = '';
        data.volumes.forEach(vol => {
            const card = document.createElement('div');
            card.className = 'ebs-card';
            card.innerHTML = `
                <h4>${vol.volume_name}</h4>
                <p>ID: ${vol.volume_id}</p>
                <p>Size: ${vol.size_gb} GB</p>
                <p>Type: ${vol.volume_type}</p>
                <p>State: ${vol.state}</p>
                <p>Attached: ${vol.attached_instance_name}</p>
                <button onclick="deleteEBS('${vol.volume_id}')">Delete</button>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = '<p>Error loading EBS volumes.</p>';
    }
}

// =============================================
// DELETE EBS
// =============================================

async function deleteEBS(volumeId) {
    if (!confirm('Delete this EBS volume?')) return;
    try {
        const res = await fetch(`/storage/ebs/delete/${volumeId}`, { method: 'DELETE' });
        const data = await res.json();
        alert(data.message);
        loadEBSVolumes();
    } catch (err) {
        alert('Error deleting EBS');
    }
}

// =============================================
// CHANGE PASSWORD
// =============================================

function changePassword() {
    alert('Change Password feature coming soon!');
}

// =============================================
// SAVE SETTINGS
// =============================================

function saveSettings() {
    alert('Settings saved!');
}

// =============================================
// CHANGE THEME
// =============================================

function changeTheme() {
    const theme = document.getElementById('theme-mode').value;
    if (theme === 'Dark') {
        document.body.style.background = '#1a1a2e';
        document.body.style.color = 'white';
    } else {
        document.body.style.background = '#f4f7fc';
        document.body.style.color = 'black';
    }
}

// =============================================
// ON PAGE LOAD
// =============================================

window.onload = function () {
    refreshInstances();
    loadKeypairs();
    loadSecurityGroups();
    loadEBSVolumes();
    loadBuckets();
};

// =============================================
// LOAD BUCKETS
// =============================================

async function loadBuckets() {
    const container = document.getElementById('buckets-container');
    container.innerHTML = '<p>Loading...</p>';

    try {
        const res = await fetch('/buckets');
        const data = await res.json();

        if (data.buckets.length === 0) {
            container.innerHTML = '<p>No buckets found.</p>';
            return;
        }

        container.innerHTML = '';
        data.buckets.forEach(bucket => {
            const card = document.createElement('div');
            card.className = 'ebs-card';
            card.innerHTML = `
                <h4><i class="fa-solid fa-bucket"></i> ${bucket.bucket_name}</h4>
                <p>Created: ${bucket.created_at}</p>
                <div style="margin-top:10px; display:flex; gap:8px;">
                    <button class="start-btn" onclick="viewFiles('${bucket.bucket_name}')">
                        <i class="fa-solid fa-folder-open"></i> View Files
                    </button>
                    <button class="terminate-btn" onclick="deleteBucket('${bucket.bucket_name}')">
                        <i class="fa-solid fa-trash"></i> Delete
                    </button>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (err) {
        container.innerHTML = '<p>Error loading buckets.</p>';
        console.error(err);
    }
}

// =============================================
// CREATE BUCKET
// =============================================

async function createBucket() {
    const bucketName = document.getElementById('bucket-name').value;

    if (!bucketName) {
        alert('Please enter a bucket name!');
        return;
    }

    try {
        const res = await fetch('/create-bucket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bucket_name: bucketName })
        });
        const data = await res.json();
        if (res.ok) {
            alert(`Bucket created: ${data.bucket_name}`);
            document.getElementById('bucket-name').value = '';
            loadBuckets();
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error creating bucket');
        console.error(err);
    }
}

// =============================================
// DELETE BUCKET
// =============================================

async function deleteBucket(bucketName) {
    if (!confirm(`Delete bucket "${bucketName}" and all its files?`)) return;

    try {
        const res = await fetch(`/delete-bucket/${bucketName}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadBuckets();
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error deleting bucket');
    }
}

// =============================================
// VIEW FILES IN BUCKET
// =============================================

async function viewFiles(bucketName) {
    document.getElementById('current-bucket-name').textContent = bucketName;
    document.getElementById('s3-files-section').style.display = 'block';
    document.getElementById('s3-files-section').dataset.bucket = bucketName;

    const container = document.getElementById('files-container');
    container.innerHTML = '<p>Loading files...</p>';

    try {
        const res = await fetch(`/files/${bucketName}`);
        const data = await res.json();

        if (data.files.length === 0) {
            container.innerHTML = '<p>No files in this bucket.</p>';
            return;
        }

        container.innerHTML = '';
        data.files.forEach(file => {
            const card = document.createElement('div');
            card.className = 'ebs-card';
            card.innerHTML = `
                <h4><i class="fa-solid fa-file"></i> ${file.file_name}</h4>
                <p>Size: ${(file.size_bytes / 1024).toFixed(2)} KB</p>
                <div style="margin-top:10px;">
                    <button class="terminate-btn" onclick="deleteFile('${bucketName}', '${file.file_name}')">
                        <i class="fa-solid fa-trash"></i> Delete
                    </button>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (err) {
        container.innerHTML = '<p>Error loading files.</p>';
    }
}

// =============================================
// UPLOAD FILE
// =============================================

async function uploadFile() {
    const bucketName = document.getElementById('s3-files-section').dataset.bucket;
    const fileInput = document.getElementById('upload-file-input');

    if (!fileInput.files[0]) {
        alert('Please select a file!');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        const res = await fetch(`/upload-file?bucket_name=${bucketName}`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            alert(`File uploaded: ${data.file_name}`);
            viewFiles(bucketName);
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error uploading file');
    }
}

// =============================================
// DELETE FILE
// =============================================

async function deleteFile(bucketName, fileName) {
    if (!confirm(`Delete file "${fileName}"?`)) return;

    try {
        const res = await fetch(`/delete-file?bucket_name=${bucketName}&file_name=${fileName}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            viewFiles(bucketName);
        } else {
            alert('Error: ' + data.detail);
        }
    } catch (err) {
        alert('Error deleting file');
    }
}