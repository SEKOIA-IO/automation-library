from elasticsearch_module import ElasticSearchModule
from elasticsearch_module.query_data_action import QueryDataAction

if __name__ == "__main__":
    module = ElasticSearchModule()

    module.register(QueryDataAction, "elasticsearch_query_data")

    module.run()
