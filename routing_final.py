from backend.providers.routing_provider import RoutingProvider
class RoutingAPI:
    def __init__(self):
        self.provider = RoutingProvider()
    def get_routes(
        self,
        origin,
        dest,
        alternatives=True,
        max_routes=3,
        transport_mode="car",
    ):
        max_routes = max(1, min(int(max_routes), 3))
        if not alternatives:
            max_routes = 1
        routes = self.provider.get_routes(
            origin=origin,
            destination=dest,
            max_routes=max_routes,
            transport_mode=transport_mode,
        )
        for index, route in enumerate(routes, 1):
            route["route_id"] = index
        return routes[:max_routes]
    def get_route(self, origin, dest, transport_mode="car"):
        routes = self.get_routes(
            origin,
            dest,
            alternatives=False,
            max_routes=1,
            transport_mode=transport_mode,
        )
        return routes[0] if routes else None
