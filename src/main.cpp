#include <crow.h>

int main()
{
	crow::SimpleApp app;

	// 定义路由
	CROW_ROUTE(app, "/")([](){
		return "Hello from c++ Web Server!";
	});

	CROW_ROUTE(app, "/user/<string>")([](std::string name){
		return "Hello, " + name;		
	});

	// 监听 0.0.0.0:8080 多线程运行
	app.port(8080).multithreaded().run();

}
