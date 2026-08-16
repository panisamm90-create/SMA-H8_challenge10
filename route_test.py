import os
import sys
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)
from api.routing import RoutingAPI
routing_api = RoutingAPI()
route = routing_api.get_route(
    origin=(34.0522, -118.2437),
    dest=(33.9416, -118.4085)
)
print(route)