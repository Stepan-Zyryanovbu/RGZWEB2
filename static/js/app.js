fetch('/api', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'user.register',
        params: {
            username: 'username',
            password: 'password',
            name: 'name',
            email: 'email',
            avatar: 'file_data'  // Пример отправки файла (в форме base64 или в другом формате)
        },
        id: 1
    })
})
.then(response => response.json())
.then(data => {
    console.log(data);
});
