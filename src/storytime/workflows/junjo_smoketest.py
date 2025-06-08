import asyncio

from junjo import BaseState, BaseStore, Graph, Node, Workflow


# Define the workflow state
class SmokeTestState(BaseState):
    message: str | None = None

# Define the workflow store
class SmokeTestStore(BaseStore[SmokeTestState]):
    async def set_message(self, payload: str) -> None:
        await self.set_state({"message": payload})

# Define a node that sets a message
class HelloNode(Node[SmokeTestStore]):
    async def service(self, store: SmokeTestStore) -> None:
        await store.set_message("Hello from Junjo!")
        print("HelloNode executed.")

# Instantiate the node
hello_node = HelloNode()

# Create the workflow graph (single node as both source and sink)
graph = Graph(
    source=hello_node,
    sink=hello_node,
    edges=[]
)

# Create the workflow
workflow = Workflow[
    SmokeTestState, SmokeTestStore
](
    name="Junjo Smoke Test Workflow",
    graph=graph,
    store=SmokeTestStore(initial_state=SmokeTestState()),
)

async def main():
    await workflow.execute()
    state = await workflow.get_state_json()
    print("Final state:", state)

if __name__ == "__main__":
    asyncio.run(main())
