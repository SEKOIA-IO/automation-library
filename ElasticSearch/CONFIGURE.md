## Configuration

To create credentials for the `ElasticSearch` integration please follow next steps:

1. Log in to your Kibana console
2. Go to `Management` > `Stack Management`
   
     ![Step 1](docs/assets/step01.png){: style="max-width:100%"}

3. In the Stack Management interface, go to `Security` > `API Keys`

     ![Step 2](docs/assets/step02.png){: style="max-width:100%"}

4. In the `API Keys` section, click `+ Create API key`

     ![Step 3](docs/assets/step03.png){: style="max-width:100%"}

5. Type a name for the API key
6. If requested by our security practices, define an expiration date for the API key. 
   
   > **_NOTE:_** Be aware that an expiration date on an API key will force you to renew the API key on a regular basis. Expired API keys will break playbooks.

7. Use the following template to define the control security privileges of the API Key
   
   ```json> 
   {
      "read-only-role": {
        "cluster": ["all"],
        "indices": [
          {
            "names": ["*"],
            "privileges": ["read"]
          }
        ]
      }
    }
   ```

8. Click `Create API key`

     ![Step 4](docs/assets/step04.png){: style="max-width:100%"}

9. Use your API key token

     ![Step 5](docs/assets/step05.png){: style="max-width:100%"}
